# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, division
from veil.profile.installer import *


ORACLE_HOME = DEPENDENCY_INSTALL_DIR / 'instantclient_12_2'
ORACLE_DRIVER_CONF_PATH = '/etc/ld.so.conf.d/oracle_driver.conf'
RESOURCE_KEY = 'veil.backend.database.oracle_driver.oracle_driver_resource'
RESOURCE_VERSION = '12.2.0.1.0'


@atomic_installer
def oracle_driver_resource():
    env = os.environ.copy()
    env['ORACLE_HOME'] = ORACLE_HOME
    dry_run_result = get_dry_run_result()
    if dry_run_result is not None:
        if is_downloading_while_dry_run():
            download_oracle_instantclient()
        dry_run_result['oracle-driver'] = '-' if is_oracle_instantclient_installed() else 'INSTALL'
    else:
        install_oracle_instantclient(env)

    install_resource(python_package_resource(name='cx_Oracle', reload_after_install=True, env=env))


def download_oracle_instantclient():
    if os.path.exists(ORACLE_HOME):
        return
    basic_local_path = DEPENDENCY_DIR / 'instantclient-basic-linux.x64-{}.zip'.format(RESOURCE_VERSION)
    if not os.path.exists(basic_local_path):
        while 1:
            try:
                shell_execute('wget --no-check-certificate -c {}/instantclient-basic-linux.x64-{}.zip -O {}'.format(DEPENDENCY_SSL_URL, RESOURCE_VERSION, basic_local_path))
            except Exception as e:
                print(e.message)
            else:
                break
    shell_execute('unzip {} -d {}'.format(basic_local_path, DEPENDENCY_INSTALL_DIR))
    sdk_local_path = DEPENDENCY_DIR / 'instantclient-sdk-linux.x64-{}.zip'.format(RESOURCE_VERSION)
    if not os.path.exists(sdk_local_path):
        while 1:
            try:
                shell_execute('wget --no-check-certificate -c {}/instantclient-sdk-linux.x64-{}.zip -O {}'.format(DEPENDENCY_SSL_URL, RESOURCE_VERSION, sdk_local_path))
            except Exception as e:
                print(e.message)
            else:
                break
    shell_execute('unzip {} -d {}'.format(sdk_local_path, DEPENDENCY_INSTALL_DIR))


def is_oracle_instantclient_installed():
    if not os.path.exists(ORACLE_DRIVER_CONF_PATH):
        return False
    with open(ORACLE_DRIVER_CONF_PATH, 'rb') as f:
        return ORACLE_HOME == f.read()


def install_oracle_instantclient(env):
    if is_oracle_instantclient_installed():
        if (VEIL_ENV.is_dev or VEIL_ENV.is_test) and RESOURCE_VERSION != get_resource_latest_version(RESOURCE_KEY):
            set_resource_latest_version(RESOURCE_KEY, RESOURCE_VERSION)
        return
    download_oracle_instantclient()
    shell_execute('ln -sf libclntsh.so.12.1 libclntsh.so', cwd=ORACLE_HOME)
    install_resource(file_resource(path=ORACLE_DRIVER_CONF_PATH, content=ORACLE_HOME))
    env['LD_LIBRARY_PATH'] = '{}:{}'.format(env.get('LD_LIBRARY_PATH', ''), ORACLE_HOME)
    shell_execute('ldconfig')
    if VEIL_ENV.is_dev or VEIL_ENV.is_test:
        set_resource_latest_version(RESOURCE_KEY, RESOURCE_VERSION)
