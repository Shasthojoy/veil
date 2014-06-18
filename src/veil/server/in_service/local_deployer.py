from __future__ import unicode_literals, print_function, division
import logging
import threading
import functools
from veil.environment import get_current_veil_server
from veil.utility.shell import *
from veil.development.git import *
from veil.frontend.cli import *

LOGGER = logging.getLogger(__name__)


@script('deploy')
def deploy():
    check_no_changes_not_committed()
    check_no_commits_not_pushed()
    shell_execute('veil install veil_installer.component_resource?veil.server.supervisor')
    shell_execute('veil down')
    shell_execute('veil install-server')
    shell_execute('veil up --daemonize')
    shell_execute('veil migrate')
    check_no_changes_not_committed()
    check_no_commits_not_pushed()


@script('patch')
def patch():
    shell_execute('veil migrate')
    threads = []
    for program_name, program in get_current_veil_server().programs.items():
        if program.get('patchable'):
            program_name = '{}:{}'.format(program['group'], program_name) if program.get('group') else program_name
            thread = threading.Thread(target=functools.partial(shell_execute, 'veil server supervisor restart-program {}'.format(program_name)))
            threads.append(thread)
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()