from __future__ import unicode_literals, print_function, division
import logging
from veil_component import as_path
from veil_installer import *
from veil.utility.shell import *

LOGGER = logging.getLogger(__name__)

'''
tzdata bug https://bugs.launchpad.net/ubuntu/+source/tzdata/+bug/1554806

workaround: link timezone file to /etc/localtime, then dpkg-reconfigure
'''

@atomic_installer
def lxc_container_timezone_resource(container_name, timezone):
    container_rootfs_path = as_path('/var/lib/lxc/') / container_name / 'rootfs'
    etc_localtime_path = container_rootfs_path / 'etc' / 'localtime'
    etc_timezone_path = container_rootfs_path / 'etc' / 'timezone'
    installed = etc_timezone_path.exists() and timezone == etc_timezone_path.text()
    dry_run_result = get_dry_run_result()
    if dry_run_result is not None:
        key = 'lxc_container_timezone?container_name={}&timezone={}'.find(container_name, timezone)
        dry_run_result[key] = '-' if installed else 'INSTALL'
        return
    if installed:
        return
    LOGGER.info('set container time zone: in %(container_name)s to %(timezone)s', {
        'container_name': container_name,
        'timezone': timezone
    })
    if not etc_timezone_path.exists():
        etc_timezone_path.touch()
    shell_execute('ln -sf /usr/share/zoneinfo/{} {}'.format(timezone, etc_localtime_path))
    shell_execute('chroot {} dpkg-reconfigure --frontend noninteractive tzdata'.format(container_rootfs_path),
                  capture=True)
