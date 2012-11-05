from __future__ import unicode_literals, print_function, division
import sys
import logging
import argparse
import pprint
from .installer import install_resources
from .installer import dry_run_install_resources
from .installer import register_installer
from .python_package_installer import install_python_package
from .os_package_installer import install_os_package
from .component_installer import install_component
from .component_installer import parse_resource
from .filesystem_installer import install_directory

logging.basicConfig(level=logging.DEBUG)

argument_parser = argparse.ArgumentParser('Install resource')
argument_parser.add_argument('resource', type=str, help='<installer_name>?<installer_arg1>&<installer_arg2>...')
argument_parser.add_argument('--dry-run', help='list the resources required and installed or not', action='store_true')
argument_parser.add_argument('--installer-provider', help='for non-builtin resource')
args = argument_parser.parse_args(sys.argv[1:])

if '?' in args.resource:
    resource = parse_resource(args.resource)
else:
    component_name = args.resource
    resource = ('component', dict(name=component_name))

register_installer('python_package', install_python_package)
register_installer('os_package', install_os_package)
register_installer('component', install_component)
register_installer('directory', install_directory)
installer_providers = [args.installer_provider] if args.installer_provider else []
if args.dry_run:
    pprint.pprint(dry_run_install_resources(installer_providers, [resource]))
else:
    install_resources(installer_providers, [resource])

