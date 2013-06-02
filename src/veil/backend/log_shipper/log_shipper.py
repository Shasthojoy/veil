from __future__ import unicode_literals, print_function, division
import time
import os
import logging
from redis.client import StrictRedis
from veil.frontend.cli import *
from veil.model.event import event
from veil.server.process import EVENT_PROCESS_TEARDOWN
from .log_shipper_installer import load_log_shipper_config

# Written according to https://github.com/josegonzalez/beaver/blob/master/beaver/worker.py

LOGGER = logging.getLogger(__name__)

shippers = []

@script('up')
def bring_up_log_shipper():
    for log_path, redis_config in load_log_shipper_config().items():
        redis_client = StrictRedis(host=redis_config.host, port=redis_config.port)
        shippers.append(LogShipper(log_path, redis_client, redis_config.key))
    while True:
        for shipper in shippers:
            try:
                shipper.ship()
            except:
                LOGGER.exception('failed to ship log: %(path)s', {'path': shipper.log_path})
        time.sleep(0.1)


@event(EVENT_PROCESS_TEARDOWN)
def close_shipper_log_files():
    for shipper in shippers:
        LOGGER.info('close shipper log file at exit: %(path)s', {'path': shipper.log_path})
        shipper.close_log_file()


class LogShipper(object):
    def __init__(self, log_path, redis_client, redis_key):
        super(LogShipper, self).__init__()
        self.log_path = log_path
        self.redis_client = redis_client
        self.redis_key = redis_key
        self.log_file_id = None
        self.log_file = None

    def ship(self):
        self.open_latest_log_file()
        if self.log_file:
            lines = self.log_file.readlines()
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    self.redis_client.rpush(self.redis_key, line)
                except:
                    LOGGER.exception('failed to push log: %(line)s, %(path)s', {
                        'line': line,
                        'path': self.log_path
                    })
                    self.wait_for_redis_back()
                    try:
                        self.redis_client.rpush(self.redis_key, line)
                    except:
                        LOGGER.exception('failed to push log again: %(line)s, %(path)s', {
                            'line': line,
                            'path': self.log_path
                        })

    def open_latest_log_file(self):
        # log path might point to different file due to log rotation
        if self.log_file:
            latest_log_file_id = load_file_id(self.log_path)
            if latest_log_file_id and latest_log_file_id != self.log_file_id:
                latest_log_file = open(self.log_path, 'r')
                self.close_log_file()
                self.log_file_id = latest_log_file_id
                self.log_file = latest_log_file
                LOGGER.info('reopened latest log file: %(path)s => %(file_id)s', {
                    'path': self.log_path,
                    'file_id': self.log_file_id
                })
        else:
            self.open_log_file()

    def open_log_file(self):
        if os.path.exists(self.log_path):
            self.log_file_id = load_file_id(self.log_path)
            self.log_file = open(self.log_path, 'r')
            LOGGER.info('opened log file: %(path)s => %(file_id)s', {
                'path': self.log_path,
                'file_id': self.log_file_id
            })
            self.log_file.seek(0, os.SEEK_END) # skip old logs, assuming we started before them

    def close_log_file(self):
        if self.log_file and not self.log_file.closed:
            try:
                self.log_file.close()
            except:
                LOGGER.exception('Cannot close log file: %(path)s', {'path': self.log_path})

    def wait_for_redis_back(self):
        while True:
            try:
                time.sleep(1)
                self.redis_client.llen(self.redis_key)
                LOGGER.info('log collector is available now')
                return
            except:
                LOGGER.exception('log collector still unavailable')

    def __repr__(self):
        return 'Shipper with log_path <{}> and redis_key <{}>'.format(self.log_path, self.redis_key)


def load_file_id(path):
    if os.path.exists(path):
        st = os.stat(path)
        return st.st_dev, st.st_ino
    else:
        return None
