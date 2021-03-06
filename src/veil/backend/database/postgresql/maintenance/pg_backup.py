from __future__ import unicode_literals, print_function, division
import os
from veil.frontend.cli import *
from veil.backend.database.client import *
from veil.utility.shell import *
from ...postgresql_setting import get_pg_bin_dir
from ..server.pg_server_installer import postgresql_maintenance_config

"""
pg_dump -h 10.24.2.30 -p 5432 -U veil -b -v -d ljmall | gzip > backup.gz
gunzip -c backup.gz | pg_restore -h localhost -p 5432 -U veil -j nproc -v -c -d ljmall

pg_dump -h 10.24.2.30 -p 5432 -U veil -j `nproc` -F d -b -v -f /home/dejavu/dump -d ljmall
pg_restore -h localhost -p 5432 -U veil -j `nproc` -F d -v -c -d ljmall /home/dejavu/dump
"""


@script('create-backup')
def create_backup(purpose, backup_path):
    config = database_client_config(purpose)
    maintenance_config = postgresql_maintenance_config(purpose)
    env = os.environ.copy()
    env['PGPASSWORD'] = config.password
    shell_execute('{pg_bin_dir}/pg_dump -h {host} -p {port} -U {user} -j `nproc` -F d -b -v -f "{backup_path}" -d {database}'.format(
        pg_bin_dir=get_pg_bin_dir(maintenance_config.version),
        host=config.host,
        port=config.port,
        user=config.user,
        backup_path=backup_path,
        database=config.database), env=env)

@script('restore-backup')
def restore_backup(backup_path, purpose):
    config = database_client_config(purpose)
    maintenance_config = postgresql_maintenance_config(purpose)
    env = os.environ.copy()
    env['PGPASSWORD'] = maintenance_config.owner_password
    shell_execute('{pg_bin_dir}/pg_restore -h {host} -p {port} -U {user} -j `nproc` -F d -v -c -d {database} "{backup_path}"'.format(
        pg_bin_dir=get_pg_bin_dir(maintenance_config.version),
        host=config.host,
        port=config.port,
        user=maintenance_config.owner,
        backup_path=backup_path,
        database=config.database), env=env)
