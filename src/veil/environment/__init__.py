from __future__ import unicode_literals, print_function, division
from .environment import VEIL_HOME
from .environment import VEIL_FRAMEWORK_HOME
from .environment import VEIL_LOG_DIR
from .environment import VEIL_ETC_DIR
from .environment import VEIL_VAR_DIR
from .environment import VEIL_SERVER
from .environment import VEIL_ENV
from .environment import VEIL_SERVER_NAME
from .environment import CURRENT_USER
from .environment import CURRENT_USER_GROUP
from .environment import CURRENT_USER_HOME
from .environment import BASIC_LAYOUT_RESOURCES
from .environment import split_veil_server_code


def veil_server(deployed_via, programs, resources=()):
    from veil.model.collection import objectify

    return objectify({
        'deployed_via': deployed_via,
        'programs': programs,
        'resources': resources
    })


def get_veil_servers(env):
    return get_application().ENVIRONMENTS[env]


def get_current_veil_server():
    return get_application().ENVIRONMENTS[VEIL_ENV][VEIL_SERVER_NAME]


def get_remote_veil_server(code):
    env, server_name = split_veil_server_code(code)
    return get_application().ENVIRONMENTS[env][server_name]


def get_application_codebase():
    return get_application().CODEBASE


def get_application_name():
    codebase = get_application_codebase()
    return codebase[codebase.find('/') + 1:].replace('.git', '')


def get_application_architecture():
    return getattr(get_application(), 'ARCHITECTURE', {})


def get_application_components():
    return get_application_architecture().keys()


def get_application_version():
    if 'development' == VEIL_SERVER:
        return 'development'
    if 'test' == VEIL_SERVER:
        return 'test'
    from veil.utility.shell import shell_execute

    app_commit_hash = shell_execute('git rev-parse HEAD', cwd=VEIL_HOME, capture=True).strip()
    framework_commit_hash = shell_execute('git rev-parse HEAD', cwd=VEIL_FRAMEWORK_HOME, capture=True).strip()
    return '{}-{}'.format(app_commit_hash, framework_commit_hash)


def get_application():
    import __veil__

    return __veil__

