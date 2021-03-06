from __future__ import unicode_literals, print_function, division
from cStringIO import StringIO
import contextlib
import os
from time import sleep
import uuid
import logging
import fabric.api
import fabric.contrib.files
from veil_component import as_path, cyan
from veil.environment import *
from veil.environment.networking import *
from veil.utility.misc import *
from veil_installer import *
from .container_installer import veil_container_resource, get_remote_file_content

LOGGER = logging.getLogger(__name__)

CURRENT_DIR = as_path(os.path.dirname(__file__))
hosts_to_install = []
sources_list_installed = []


@composite_installer
def veil_hosts_resource(veil_env_name, config_dir):
    resources = []
    hosts = list_veil_hosts(veil_env_name)
    for host in hosts:
        fabric.api.env.host_string = host.deploys_via
        if is_initialized_for_another_same_base_instance(host):
            raise Exception(
                'Can not deploy {} on host {} as it is initialized for another same-base instance!!!'.format(
                    host.VEIL_ENV.name, host.name))
        if host.base_name not in hosts_to_install:
            resources.extend([
                veil_host_onetime_config_resource(host=host),
                veil_host_config_resource(host=host, config_dir=config_dir),
                veil_host_application_config_resource(host=host, config_dir=config_dir),
                veil_host_codebase_resource(host=host)
            ])
            host_users_dir = as_path(config_dir / host.VEIL_ENV.name / 'hosts' / host.base_name / 'USERS')
            if host_users_dir.exists():
                print(cyan('Install Veil host users resource'))
                for user_dir in host_users_dir.dirs():
                    resources.append(veil_host_user_resource(host=host, user_dir=user_dir))
            if any(h.with_user_editor for h in hosts if h.base_name == host.base_name):
                print(cyan('Install Veil host user editor resource'))
                resources.append(veil_host_user_editor_additional_resource(host=host))
            resources.append(veil_host_iptables_rules_resource(host=host))
            hosts_to_install.append(host.base_name)
        for server in host.server_list:
            resources.extend([
                veil_host_directory_resource(host=host, remote_path=server.etc_dir),
                veil_host_directory_resource(host=host, remote_path=server.log_dir, owner=host.ssh_user, owner_group=host.ssh_user_group, mode=0755),
                veil_container_resource(host=host, server=server, config_dir=config_dir)
            ])
    return resources


@composite_installer
def veil_hosts_codebase_resource(veil_env_name):
    resources = []
    for host in unique(list_veil_hosts(veil_env_name), id_func=lambda h: h.base_name):
        fabric.api.env.host_string = host.deploys_via
        resources.append(veil_host_codebase_resource(host=host))
    return resources


def render_iptables_rules_installer_file(host):
    resources = []
    ssh_ports = set()
    for h in list_veil_hosts(host.VEIL_ENV.name):
        if h.base_name != host.base_name:
            continue
        resources.append(iptables_rule_resource(table='nat', rule='POSTROUTING -s {}.0/24 ! -d {}.0/24 -j MASQUERADE'.format(h.lan_range, h.lan_range)))
        resources.extend(h.iptables_rule_resources)
        ssh_ports.add(host.ssh_port)
    resources.extend(list_iptables_resources_to_secure_host(ssh_ports))
    return '\n'.join(to_resource_code(resource) for resource in resources)


@atomic_installer
def veil_host_iptables_rules_resource(host):
    remote_installer_file_content = get_remote_file_content(host.installed_iptables_rules_installer_path)
    installer_file_content = render_iptables_rules_installer_file(host)
    if remote_installer_file_content:
        action = None if installer_file_content == remote_installer_file_content else 'UPDATE'
    else:
        action = 'INSTALL'
    dry_run_result = get_dry_run_result()
    if dry_run_result is not None:
        key = 'veil_host_iptables_rules?{}'.format(host.VEIL_ENV.name)
        dry_run_result[key] = action or '-'
        return
    if not action:
        return
    with contextlib.closing(StringIO(installer_file_content)) as f:
        fabric.api.put(f, host.iptables_rules_installer_path, use_sudo=True, mode=0600)
    with fabric.api.cd(host.veil_home):
        fabric.api.sudo('veil :{} install veil_installer.installer_resource?{}'.format(host.VEIL_ENV.name, host.iptables_rules_installer_path))
        fabric.api.sudo('iptables-save -c > /etc/iptables.rules')
    fabric.api.sudo('mv -f {} {}'.format(host.iptables_rules_installer_path, host.installed_iptables_rules_installer_path))


@composite_installer
def veil_host_onetime_config_resource(host):
    initialized = fabric.contrib.files.exists(host.initialized_tag_link)
    if initialized:
        return []

    resources = [
        veil_host_file_resource(local_path=CURRENT_DIR / 'iptablesload', host=host, remote_path='/etc/network/if-pre-up.d/iptablesload', owner='root',
                                owner_group='root', mode=0755),
        veil_host_file_resource(local_path=CURRENT_DIR / 'iptablessave', host=host, remote_path='/etc/network/if-post-down.d/iptablessave', owner='root',
                                owner_group='root', mode=0755),
        veil_host_file_resource(local_path=CURRENT_DIR / 'sudoers.d.ssh-auth-sock', host=host, remote_path='/etc/sudoers.d/ssh-auth-sock', owner='root',
                                owner_group='root', mode=0440),
        veil_host_file_resource(local_path=CURRENT_DIR / 'ipv4-ip-forward.conf', host=host, remote_path='/etc/sysctl.d/60-lxc-ipv4-ip-forward.conf',
                                owner='root', owner_group='root', mode=0644, cmd='sysctl -p /etc/sysctl.d/60-lxc-ipv4-ip-forward.conf'),
        veil_host_file_resource(local_path=CURRENT_DIR / 'disable-ipv6.conf', host=host, remote_path='/etc/sysctl.d/60-disable-ipv6.conf',
                                owner='root', owner_group='root', mode=0644, cmd='sysctl -p /etc/sysctl.d/60-disable-ipv6.conf'),
        veil_host_sources_list_resource(host=host),
        veil_host_init_resource(host=host)
    ]
    return resources


@composite_installer
def veil_host_config_resource(host, config_dir):
    env_config_dir = config_dir / host.VEIL_ENV.name
    resources = [
        veil_host_directory_resource(host=host, remote_path='/home/{}/.ssh'.format(host.ssh_user), owner=host.ssh_user, owner_group=host.ssh_user_group,
                                     mode=0700),
        veil_host_file_resource(local_path=env_config_dir / '.ssh' / 'authorized_keys', host=host,
                                remote_path='/home/{}/.ssh/authorized_keys'.format(host.ssh_user), owner=host.ssh_user, owner_group=host.ssh_user_group,
                                mode=0600),
        veil_host_file_resource(local_path=CURRENT_DIR / 'apt-config', host=host, remote_path='/etc/apt/apt.conf.d/99-veil-apt-config', owner='root',
                                owner_group='root', mode=0644),
        veil_host_sources_list_resource(host=host)
    ]

    servers = get_veil_env(host.VEIL_ENV.name).servers
    if 'guard' in servers:
        resources.extend([
            veil_host_directory_resource(host=host, remote_path='/root/.ssh', owner='root', owner_group='root', mode=0700),
            veil_host_file_resource(local_path=env_config_dir / '.ssh-guard' / 'id_rsa.pub', host=host, remote_path='/root/.ssh/authorized_keys', owner='root',
                                    owner_group='root', mode=0600)
        ])
    if 'monitor' in servers:
        resources.append(
            veil_host_file_resource(local_path=CURRENT_DIR / 'max-map-count.conf', host=host, remote_path='/etc/sysctl.d/60-max-map-count.conf',
                                    owner='root', owner_group='root', mode=0644, cmd='sysctl -p /etc/sysctl.d/60-max-map-count.conf'),
        )
    return resources


@composite_installer
def veil_host_application_config_resource(host, config_dir):
    env_config_dir = config_dir / host.VEIL_ENV.name
    if not (env_config_dir / '.config').exists():
        return []
    return [
        veil_host_file_resource(local_path=env_config_dir / '.config', host=host, remote_path=host.code_dir / '.config', owner=host.ssh_user,
                                owner_group=host.ssh_user_group, mode=0600)
    ]


@atomic_installer
def veil_host_codebase_resource(host):
    dry_run_result = get_dry_run_result()
    if dry_run_result is not None:
        key = 'veil_host_codebase?{}'.format(host.VEIL_ENV.name)
        dry_run_result[key] = 'INSTALL'
        return
    with fabric.api.settings(forward_agent=True):
        clone_application(host)
        pull_application(host)
        clone_framework(host)
        pull_framework(host)
    init_application(host)


def clone_application(host):
    if fabric.contrib.files.exists(host.veil_home):
        return
    fabric.api.sudo('git clone -b {} --depth=1 {} {}'.format(host.veil_application_branch, get_application_codebase(),
                                                             host.veil_home))


def clone_framework(host):
    if fabric.contrib.files.exists(host.veil_framework_home):
        return
    fabric.api.sudo('git clone --depth=1 {} {}'.format(VEIL_FRAMEWORK_CODEBASE, host.veil_framework_home))


def pull_application(host):
    with fabric.api.cd(host.veil_home):
        while True:
            try:
                fabric.api.sudo('git pull --rebase')
            except Exception:
                sleep(1)
                continue
            else:
                break


def pull_framework(host):
    with fabric.api.cd(host.veil_framework_home):
        fabric.api.sudo('git checkout {}'.format(read_veil_framework_version(host)))
        while True:
            try:
                fabric.api.sudo('git pull --rebase')
            except Exception:
                sleep(1)
                continue
            else:
                break


def init_application(host):
    with fabric.api.cd(host.veil_home):
        fabric.api.sudo('{}/bin/veil :{} init'.format(host.veil_framework_home, host.VEIL_ENV.name))


def read_veil_framework_version(host):
    return get_remote_file_content(host.veil_home / 'VEIL-VERSION') or 'master'


@atomic_installer
def veil_host_init_resource(host):
    dry_run_result = get_dry_run_result()
    if dry_run_result is not None:
        key = 'veil_host_init?{}'.format(host.VEIL_ENV.name)
        dry_run_result[key] = 'INSTALL'
        return

    fabric.contrib.files.append('/etc/ssh/sshd_config', host.sshd_config or ['PasswordAuthentication no',
                                                                             'PermitRootLogin without-password'],
                                use_sudo=True)
    fabric.api.sudo('systemctl reload-or-restart ssh')

    fabric.api.sudo('apt update')
    fabric.api.sudo('apt -y upgrade')
    fabric.api.sudo('apt -y purge ntp whoopsie network-manager')
    install_os_packages = ['apt-transport-https', 'ntpdate', 'unattended-upgrades', 'update-notifier-common',
                           'iptables', 'git', 'language-pack-en', 'unzip', 'wget', 'python', 'python-dev', 'python-pip',
                           'python-virtualenv', 'lxc']
    fabric.api.sudo('apt -y install {}'.format(' '.join(install_os_packages)))
    # enable time sync on lxc hosts, and which is shared among lxc guests
    fabric.api.sudo(
        '''printf '#!/bin/sh\n/usr/sbin/ntpdate ntp.ubuntu.com time.nist.gov' > /etc/cron.hourly/ntpdate && chmod 0755 /etc/cron.hourly/ntpdate''')

    init_veil_host_basic_layout(host)

    fabric.api.sudo('pip install --upgrade "pip>=9.0.1"')
    fabric.api.sudo('pip install -i {} --trusted-host {} --upgrade "setuptools>=34.2.0"'.format(host.pypi_index_url, host.pypi_index_host))
    fabric.api.sudo('pip install -i {} --trusted-host {} --upgrade "wheel>=0.30.0a0"'.format(host.pypi_index_url, host.pypi_index_host))
    fabric.api.sudo('pip install -i {} --trusted-host {} --upgrade "virtualenv>=15.1.0"'.format(host.pypi_index_url, host.pypi_index_host))

    install_resource(veil_lxc_config_resource(host=host))

    fabric.api.sudo('touch {}'.format(host.initialized_tag_path))
    if host.initialized_tag_path != host.initialized_tag_link:
        fabric.api.sudo('ln -s {} {}'.format(host.initialized_tag_path, host.initialized_tag_link))


def init_veil_host_basic_layout(host):
    fabric.api.sudo('mkdir -p -m 0755 {}'.format(' '.join([
        host.opt_dir, host.share_dir, DEPENDENCY_DIR, DEPENDENCY_INSTALL_DIR, PYPI_ARCHIVE_DIR, host.env_dir,
        host.code_dir, host.etc_dir, host.log_dir, host.var_dir, host.buckets_dir, host.bucket_log_dir, host.data_dir
    ])))
    fabric.api.sudo('chown {}:{} {} {} {}'.format(host.ssh_user, host.ssh_user_group, host.buckets_dir, host.bucket_log_dir, host.data_dir))
    if host.VEIL_ENV.name != host.VEIL_ENV.base_name:
        fabric.api.sudo('ln -sfT {} {}'.format(host.env_dir, host.env_dir.parent / host.VEIL_ENV.name))


def is_initialized_for_another_same_base_instance(host):
    return host.initialized_tag_link != host.initialized_tag_path \
           and fabric.contrib.files.exists(host.initialized_tag_link) \
           and not fabric.contrib.files.exists(host.initialized_tag_path)


@atomic_installer
def veil_host_sources_list_resource(host):
    if host.base_name in sources_list_installed:
        return

    dry_run_result = get_dry_run_result()
    if dry_run_result is not None:
        key = 'veil_host_sources_list?{}'.format(host.VEIL_ENV.name)
        dry_run_result[key] = 'INSTALL'
        return
    sources_list_path = '/etc/apt/sources.list'
    fabric.api.sudo('cp -pn {path} {path}.origin'.format(path=sources_list_path))
    context = dict(mirror=host.apt_url, codename=fabric.api.run('lsb_release -cs'))
    fabric.contrib.files.upload_template('sources.list.j2', sources_list_path, context=context, use_jinja=True, template_dir=CURRENT_DIR, use_sudo=True,
                                         backup=False, mode=0644)
    fabric.api.sudo('chown root:root {}'.format(sources_list_path))

    sources_list_installed.append(host.base_name)


@atomic_installer
def veil_lxc_config_resource(host):
    dry_run_result = get_dry_run_result()
    if dry_run_result is not None:
        key = 'veil_lxc_config?{}'.format(host.VEIL_ENV.name)
        dry_run_result[key] = 'INSTALL'
        return

    lxc_config_path = '/etc/default/lxc'
    fabric.api.sudo('cp -pn {path} {path}.origin'.format(path=lxc_config_path))
    fabric.contrib.files.upload_template('lxc.j2', lxc_config_path, context=dict(mirror=host.apt_url), use_jinja=True, template_dir=CURRENT_DIR, use_sudo=True,
                                         backup=False, mode=0644)
    fabric.api.sudo('chown root:root {}'.format(lxc_config_path))
    install_resource(
        veil_host_file_resource(local_path=CURRENT_DIR / 'lxc-net', host=host, remote_path='/etc/default/lxc-net', owner='root', owner_group='root', mode=0644,
                                keep_origin=True))


@atomic_installer
def veil_host_directory_resource(host, remote_path, owner='root', owner_group='root', mode=0755):
    dry_run_result = get_dry_run_result()
    if dry_run_result is not None:
        key = 'veil_host_directory?{}&path={}'.format(host.VEIL_ENV.name, remote_path)
        dry_run_result[key] = 'INSTALL'
        return
    fabric.api.sudo('mkdir -p {}'.format(remote_path))
    fabric.api.sudo('chmod {:o} {}'.format(mode, remote_path))
    fabric.api.sudo('chown {}:{} {}'.format(owner, owner_group, remote_path))


@atomic_installer
def veil_host_file_resource(local_path, host, remote_path, owner, owner_group, mode, keep_origin=False, set_owner_first=False, cmd=None):
    dry_run_result = get_dry_run_result()
    if dry_run_result is not None:
        key = 'veil_host_file?{}&path={}'.format(host.VEIL_ENV.name, remote_path)
        dry_run_result[key] = 'INSTALL'
        return
    if keep_origin:
        fabric.api.sudo('cp -pn {path} {path}.origin'.format(path=remote_path))
    if set_owner_first:
        temp_file = '/tmp/{}'.format(uuid.uuid4().get_hex())
        fabric.api.put(local_path, temp_file, use_sudo=True, mode=mode)
        fabric.api.sudo('chown {}:{} {}'.format(owner, owner_group, temp_file))
        fabric.api.sudo('mv -f {} {}'.format(temp_file, remote_path))
    else:
        fabric.api.put(local_path, remote_path, use_sudo=True, mode=mode)
        fabric.api.sudo('chown {}:{} {}'.format(owner, owner_group, remote_path))
    if cmd:
        fabric.api.sudo(cmd)


@atomic_installer
def veil_host_user_resource(host, user_dir):
    username = user_dir.basename()
    initialized_file_path = '/home/{}/.veil_host_user_initialized'.format(username)
    installed = fabric.contrib.files.exists(initialized_file_path, use_sudo=True)
    dry_run_result = get_dry_run_result()
    if dry_run_result is not None:
        key = 'veil_host_user_{}?{}'.format(username, host.VEIL_ENV.name)
        dry_run_result[key] = '-' if installed else 'INSTALL'
        return

    if not installed:
        ret = fabric.api.run('getent passwd {}'.format(username), warn_only=True)
        if ret.failed:
            uid = (user_dir / 'id').text().strip()
            fabric.api.sudo('adduser --uid {uid} {username} --gecos {username} --disabled-login --shell /usr/sbin/nologin --quiet'.format(username=username, uid=uid))
    fabric.api.put(local_path=user_dir, remote_path='/home/', use_sudo=True, mode=0755)
    user_ssh_dir = user_dir / '.ssh'
    if user_ssh_dir.isdir():
        fabric.api.sudo('chmod 0700 /home/{}/.ssh'.format(username))
        if user_ssh_dir.listdir():
            fabric.api.sudo('chmod 0600 /home/{}/.ssh/*'.format(username))
    fabric.api.sudo('chown -R {username}:{username} /home/{username}/'.format(username=username))
    if not installed:
        fabric.api.sudo('touch {}'.format(initialized_file_path))


@atomic_installer
def veil_host_user_editor_additional_resource(host):
    installed = fabric.contrib.files.contains('/etc/ssh/sshd_config', 'Match User editor')
    dry_run_result = get_dry_run_result()
    if dry_run_result is not None:
        key = 'veil_host_user_editor?{}'.format(host.VEIL_ENV.name)
        dry_run_result[key] = '-' if installed else 'INSTALL'
        return

    if not fabric.contrib.files.exists(host.editorial_dir, use_sudo=True):
        # user `editor` creation is done by veil_host_user_resource
        fabric.api.sudo('mkdir -p -m 0755 {}'.format(host.editorial_dir))
        fabric.api.sudo('chown -R editor:editor {}'.format(host.editorial_dir))

    if installed:
        return

    # do not add any config after Match User unless you know what you write
    fabric.contrib.files.append('/etc/ssh/sshd_config',
                                ['Match User editor', 'ChrootDirectory {}'.format(host.editorial_dir.parent),
                                 'ForceCommand internal-sftp'], use_sudo=True)
    fabric.api.sudo('systemctl reload-or-restart ssh.service')
