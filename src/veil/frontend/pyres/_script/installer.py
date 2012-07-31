from __future__ import unicode_literals, print_function, division
from veil.frontend.script import *
from veil.environment.deployment import *
from veil.frontend.template import *


@script('install')
def install_pyres():
    settings = get_deployment_settings()
    install_ubuntu_package('python2.7-dev')
    execute_script('backend', 'redis', 'client', 'install')
    execute_script('backend', 'redis', 'server', 'install', 'queue')
    install_python_package('pyres')
    install_python_package('croniter')
    install_python_package('resweb')
    create_file(settings.resweb.config_file, content=get_template('resweb.cfg.j2').render(config=settings.resweb))