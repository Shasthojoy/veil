from __future__ import unicode_literals, print_function, division
import sys
from veil.profile.installer import *
from ...postgresql_setting import get_pg_config_dir, get_pg_data_dir, get_pg_bin_dir

LOGGER = logging.getLogger(__name__)


@composite_installer
def postgresql_server_resource(purpose, config):
    upgrading = False
    maintenance_config = postgresql_maintenance_config(purpose, must_exist=False)
    if maintenance_config and maintenance_config.version != config.version:
        assert maintenance_config.version < config.version, 'cannot downgrade postgresql server from {} to {}'.format(maintenance_config.version,
            config.version)
        upgrading = True
        LOGGER.warn('Start to install new-version postgresql server: %(old_version)s => %(new_version)s', {
            'old_version': maintenance_config.version,
            'new_version': config.version
        })

    pg_data_dir = get_pg_data_dir(purpose, config.version)
    pg_config_dir = get_pg_config_dir(purpose, config.version)
    resources = list(BASIC_LAYOUT_RESOURCES)
    resources.extend([
        postgresql_apt_repository_resource(),
        os_package_resource(name='postgresql-{}'.format(config.version)),
        os_service_resource(state='not_installed', name='postgresql'),
        postgresql_cluster_resource(purpose=purpose, version=config.version, owner=config.owner, owner_password=config.owner_password),
        directory_resource(path=pg_config_dir),
        file_resource(
            path=pg_config_dir / 'postgresql.conf',
            content=render_config('postgresql.conf.j2', config={
                'version': config.version,
                'data_directory': pg_data_dir,
                'host': config.host,
                'port': config.port,
                'log_destination': 'csvlog',
                'logging_collector': True,
                'log_directory': VEIL_LOG_DIR / '{}-postgresql'.format(purpose.replace('_', '-')),
                'shared_buffers': config.shared_buffers,
                'work_mem': config.work_mem,
                'maintenance_work_mem': config.maintenance_work_mem,
                'effective_io_concurrency': config.effective_io_concurrency,
                'wal_buffers': config.wal_buffers,
                'checkpoint_segments': config.checkpoint_segments,
                'checkpoint_completion_target': config.checkpoint_completion_target,
                'effective_cache_size': config.effective_cache_size,
                'log_min_duration_statement': config.log_min_duration_statement,
                'log_filename': config.get('log_filename')
            })),
        file_resource(path=pg_config_dir / 'pg_hba.conf', content=render_config('pg_hba.conf.j2', host=config.host)),
        file_resource(path=pg_config_dir / 'pg_ident.conf', content=render_config('pg_ident.conf.j2')),
        file_resource(path=pg_config_dir / 'postgresql-maintenance.cfg', content=render_config(
            'postgresql-maintenance.cfg.j2', version=config.version, owner=config.owner, owner_password=config.owner_password)),
        symbolic_link_resource(path=get_pg_config_dir(purpose), to=pg_config_dir),
        symbolic_link_resource(path=pg_data_dir / 'postgresql.conf', to=pg_config_dir / 'postgresql.conf'),
        symbolic_link_resource(path=pg_data_dir / 'pg_hba.conf', to=pg_config_dir / 'pg_hba.conf'),
        symbolic_link_resource(path=pg_data_dir / 'pg_ident.conf', to=pg_config_dir / 'pg_ident.conf'),
    ])
    if upgrading:
        resources.extend([
            os_package_resource(name='postgresql-server-dev-{}'.format(config.version)),
            postgresql_server_upgrading_resource(purpose=purpose, owner=config.owner, old_version=maintenance_config.version,
                new_version=config.version)
        ])
    resources.extend([
        postgresql_user_resource(purpose=purpose, version=config.version, user=config.user, password=config.password,
            owner=config.owner, owner_password=config.owner_password, host=config.host, port=config.port),
        postgresql_user_resource(purpose=purpose, version=config.version, user='readonly', password='r1adonly',
            owner=config.owner, owner_password=config.owner_password, host=config.host, port=config.port)
    ])

    return resources


@atomic_installer
def postgresql_server_upgrading_resource(purpose, owner, old_version, new_version):
    upgrade_postgresql_server(purpose, owner, old_version, new_version, check_only=True)
    if not confirm_upgrading(old_version, new_version):
        return
    upgrade_postgresql_server(purpose, owner, old_version, new_version, check_only=False)
    display_post_upgrade_instructions()


def upgrade_postgresql_server(purpose, owner, old_version, new_version, check_only=True):
    if check_only:
        LOGGER.warn('Checking postgresql server upgrading: %(old_version)s => %(new_version)s', {'old_version': old_version, 'new_version': new_version})
    else:
        LOGGER.warn('Upgrading postgresql server: %(old_version)s => %(new_version)s', {'old_version': old_version, 'new_version': new_version})
    shell_execute('''
        su {pg_data_owner} -c '{new_bin_dir}/pg_upgrade {check_only} -v -j {cpu_cores} -u {pg_data_owner} -b {old_bin_dir} -B {new_bin_dir} -d {old_data_dir} -D {new_data_dir} -o "-c config_file={old_data_dir}/postgresql.conf" -O "-c config_file={new_data_dir}/postgresql.conf"'
        '''.format(
        pg_data_owner=owner, check_only='-c' if check_only else '', cpu_cores=shell_execute('nproc', capture=True),
        old_bin_dir=get_pg_bin_dir(old_version), old_data_dir=get_pg_data_dir(purpose, old_version),
        new_bin_dir=get_pg_bin_dir(new_version), new_data_dir=get_pg_data_dir(purpose, new_version)
    ), capture=True)


def confirm_upgrading(old_version, new_version):
    msg_to_upgrade = 'upgrade postgresql server from {} to {}'.format(old_version, new_version)
    msg_to_not_upgrade = 'cancel upgrading'
    print('type "{}" to continue or "{}" to not upgrade:'.format(msg_to_upgrade, msg_to_not_upgrade))
    while True:
        instruction = sys.stdin.readline().strip()
        if msg_to_upgrade == instruction:
            return True
        elif msg_to_not_upgrade == instruction:
            return False


def display_post_upgrade_instructions():
    print('!!! IMPORTANT !!!')
    print('''Please do the following post-Upgrade processing:
        1.Run scripts generated by pg_upgrade, including but not limit to analyze_new_cluster.sh
        2.Verify the application
        3.Delete old cluster: config and data directories
        4.Remove the installation of the old-version postgresql server
        ''')
    print('type "i will do it" without space to continue:')
    while True:
        if 'iwilldoit' == sys.stdin.readline().strip():
            break


@atomic_installer
def postgresql_cluster_resource(purpose, version, owner, owner_password):
    pg_data_dir = get_pg_data_dir(purpose, version)
    is_installed = pg_data_dir.exists()
    dry_run_result = get_dry_run_result()
    if dry_run_result is not None:
        dry_run_result['postgresql_initdb?{}'.format(purpose)] = '-' if is_installed else 'INSTALL'
        return
    if is_installed:
        return
    LOGGER.info('install postgresql cluster: for %(purpose)s, %(version)s', {'purpose': purpose, 'version': version})
    old_permission = shell_execute("stat -c '%a' {}".format(pg_data_dir.parent), capture=True)
    shell_execute('chmod 777 {}'.format(pg_data_dir.parent), capture=True)
    install_resource(file_resource(path='/tmp/pg-{}-owner-password'.format(purpose), content=owner_password))
    try:
        shell_execute(
            'su {pg_data_owner} -c "{pg_bin_dir}/initdb -E UTF-8 --locale=POSIX -A md5 -U {pg_data_owner} --pwfile=/tmp/pg-{purpose}-owner-password {pg_data_dir}"'.format(
                pg_data_owner=owner, pg_bin_dir=get_pg_bin_dir(version), pg_data_dir=pg_data_dir, purpose=purpose
            ), capture=True)
        shell_execute('mv postgresql.conf postgresql.conf.origin', cwd=pg_data_dir)
        shell_execute('mv pg_hba.conf pg_hba.conf.origin', cwd=pg_data_dir)
        shell_execute('mv pg_ident.conf pg_ident.conf.origin', cwd=pg_data_dir)
    finally:
        delete_file('/tmp/pg-{}-owner-password'.format(purpose))
        shell_execute('chmod {} {}'.format(old_permission, pg_data_dir.parent), capture=True)


@atomic_installer
def postgresql_user_resource(purpose, version, user, password, owner, owner_password, host, port):
    pg_user = user
    assert pg_user, 'must specify postgresql user'
    pg_password = password
    assert pg_password, 'must specify postgresql user password'
    pg_data_dir = get_pg_data_dir(purpose, version)
    user_installed_tag_file = pg_data_dir / 'user-{}-installed'.format(user)
    is_installed = user_installed_tag_file.exists()
    dry_run_result = get_dry_run_result()
    if dry_run_result is not None:
        dry_run_result['postgresql_user?{}'.format(purpose)] = '-' if is_installed else 'INSTALL'
        return
    if is_installed:
        return
    LOGGER.info('install postgresql user: %(user)s in %(purpose)s', {'user': user, 'purpose': purpose})
    pg_bin_dir = get_pg_bin_dir(version)
    with postgresql_server_running(version, pg_data_dir, owner):
        env = os.environ.copy()
        env['PGPASSWORD'] = owner_password
        if not postgresql_user_existed(version, host, port, owner, pg_user, env):
            shell_execute('''
                {}/psql -h {} -p {} -U {} -d postgres -c "CREATE USER {} WITH PASSWORD '{}'"
                '''.format(pg_bin_dir, host, port, owner, pg_user, pg_password), env=env, capture=True)
        user_installed_tag_file.touch()


def postgresql_user_existed(version, host, port, owner, username, env):
    return '1' == shell_execute('''
        {}/psql -h {} -p {} -U {} -d postgres -tAc "SELECT 1 FROM pg_user WHERE usename='{}'"
        '''.format(get_pg_bin_dir(version), host, port, owner, username), env=env, capture=True)


def delete_file(path):
    if os.path.exists(path):
        LOGGER.info('delete file: %(path)s', {'path': path})
        os.remove(path)


@contextlib.contextmanager
def postgresql_server_running(version, data_directory, owner):
    pg_bin_dir = get_pg_bin_dir(version)
    shell_execute('su {} -c "{}/pg_ctl -D {} start"'.format(owner, pg_bin_dir, data_directory))
    time.sleep(5)
    try:
        yield
    finally:
        shell_execute('su {} -c "{}/pg_ctl -D {} stop"'.format(owner, pg_bin_dir, data_directory))


_maintenance_config = {}
def postgresql_maintenance_config(purpose, must_exist=True):
    if purpose not in _maintenance_config:
        _maintenance_config[purpose] = load_postgresql_maintenance_config(purpose, must_exist)
    return _maintenance_config[purpose]


def load_postgresql_maintenance_config(purpose, must_exist):
    maintenance_config_path = get_pg_config_dir(purpose) / 'postgresql-maintenance.cfg'
    if not must_exist and not maintenance_config_path.exists():
        return DictObject()
    return load_config_from(maintenance_config_path, 'version', 'owner', 'owner_password')
