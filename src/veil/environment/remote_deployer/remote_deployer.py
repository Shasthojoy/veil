from __future__ import unicode_literals, print_function, division
import logging
from veil.frontend.cli import *
from veil.environment import *
from veil.utility.shell import *
import os
import datetime
import fabric.api

PAYLOAD = os.path.join(os.path.dirname(__file__), 'remote_deployer_payload.py')
GUARD = os.path.join(os.path.dirname(__file__), 'remote_deployer_guard.py')
LOGGER = logging.getLogger(__name__)

@script('deploy-env')
def deploy_env(deploying_env, from_branch=None):
    update_branch(deploying_env, from_branch)
    for deploying_server_name in sorted(get_veil_servers(deploying_env).keys()):
        guard_do('create-backup', deploying_env, deploying_server_name)
    for deploying_server_name in sorted(get_veil_servers(deploying_env).keys()):
        deploy_server(deploying_env, deploying_server_name)
    for deploying_server_name in sorted(get_veil_servers(deploying_env).keys()):
        guard_do('delete-backup', deploying_env, deploying_server_name)
    if not from_branch:
        tag_deploy(deploying_env)
    local_env_config_dir = CURRENT_USER_HOME / '.{}'.format(deploying_env)
    local_env_config_dir.rmtree()


@script('rollback-env')
def rollback_env(deploying_env):
    for deploying_server_name in sorted(get_veil_servers(deploying_env).keys()):
        guard_do('check-backup', deploying_env, deploying_server_name)
    for deploying_server_name in sorted(get_veil_servers(deploying_env).keys()):
        guard_do('rollback', deploying_env, deploying_server_name)
    for deploying_server_name in sorted(get_veil_servers(deploying_env).keys()):
        guard_do('delete-backup', deploying_env, deploying_server_name)


def guard_do(action, deploying_env, deploying_server_name):
    deployed_via = get_remote_veil_server(deploying_env, deploying_server_name).deployed_via
    fabric.api.env.host_string = deployed_via
    fabric.api.put(GUARD, '/opt/remote_deployer_guard.py', use_sudo=True, mode=0700)
    fabric.api.sudo('python /opt/remote_deployer_guard.py {} {} {}'.format(
        action,
        deploying_env,
        deploying_server_name))


def deploy_server(deploying_env, deploying_server_name):
    deployed_via = get_remote_veil_server(deploying_env, deploying_server_name).deployed_via
    fabric.api.env.host_string = deployed_via
    fabric.api.put(PAYLOAD, '/opt/remote_deployer_payload.py', use_sudo=True, mode=0700)
    local_env_config_dir = CURRENT_USER_HOME / '.{}'.format(deploying_env)
    if local_env_config_dir.exists():
        for f in local_env_config_dir.listdir():
            fabric.api.put(f, '~', mode=0600)
    fabric.api.sudo('python /opt/remote_deployer_payload.py {} {} {}'.format(
        get_application_codebase(),
        deploying_env,
        deploying_server_name))


def update_branch(deploying_env, from_branch):
    from_branch = from_branch or 'master'
    LOGGER.info('update env-{} branch...'.format(deploying_env))
    shell_execute('git checkout env-{}'.format(deploying_env), cwd=VEIL_HOME)
    shell_execute('git merge {} --ff-only'.format(from_branch), cwd=VEIL_HOME)
    shell_execute('git push origin env-{}'.format(deploying_env), cwd=VEIL_HOME)
    shell_execute('git checkout {}'.format(from_branch), cwd=VEIL_HOME)


def tag_deploy(deploying_env):
    tag_name = 'deploy-{}-{}'.format(deploying_env, datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S'))
    shell_execute('git tag {}'.format(tag_name))
    shell_execute('git push origin tag {}'.format(tag_name))