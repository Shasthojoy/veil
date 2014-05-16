from __future__ import unicode_literals, print_function, division
import logging
from veil_installer import *
from veil.utility.shell import *
from veil_component import *
from .os_package_installer import os_package_resource

LOGGER = logging.getLogger(__name__)
ETC_APT = as_path('/etc/apt')
POSTGRESQL_APT_REPOSITORY_NAME = 'pgdg'


@atomic_installer
def os_ppa_repository_resource(name):
    is_installed = is_os_package_repository_installed(name)
    dry_run_result = get_dry_run_result()
    if dry_run_result is not None:
        install_resource(os_package_resource(name='python-software-properties'))  # add-apt-repository is in the package python-software-properties
        dry_run_result['os_ppa_repository?{}'.format(name)] = '-' if is_installed else 'INSTALL'
        return
    install_resource(os_package_resource(name='python-software-properties'))  # add-apt-repository is in the package python-software-properties
    if is_installed:
        return
    LOGGER.info('installing os package repository: %(name)s ...', {'name': name})
    shell_execute('add-apt-repository ppa:{} -y'.format(name), capture=True)


@atomic_installer
def postgresql_apt_repository_resource():
    is_installed = is_os_package_repository_installed(POSTGRESQL_APT_REPOSITORY_NAME)
    dry_run_result = get_dry_run_result()
    if dry_run_result is not None:
        dry_run_result['postgresql_apt_repository?{}'.format(POSTGRESQL_APT_REPOSITORY_NAME)] = '-' if is_installed else 'INSTALL'
        return
    if is_installed:
        return
    LOGGER.info('installing postgresql apt repository: %(name)s ...', {'name': POSTGRESQL_APT_REPOSITORY_NAME})
    shell_execute('echo "deb http://apt.postgresql.org/pub/repos/apt/ `lsb_release -cs`-{name} main" > /etc/apt/sources.list.d/{name}.list'.format(
        name=POSTGRESQL_APT_REPOSITORY_NAME), capture=True)
    shell_execute('wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add -', capture=True)


def is_os_package_repository_installed(name):
    for path in (ETC_APT / 'sources.list.d').files():
        if name in path.text():
            return True
    if name in (ETC_APT / 'sources.list').text():
        return True
    return False
