from __future__ import unicode_literals, print_function, division
import os
import zipfile
from veil_component import *
from veil.utility.shell import *

PACKAGE_SUFFIX = '.tar.gz'

def download_package(package, **kwargs):
# modified from https://github.com/wolever/pip2pi/blob/master/libpip2pi/commands.py
    outdir = as_path('/opt/pypi')
    if not outdir.exists():
        outdir.mkdir()

    tempdir = outdir / '_temp'
    if tempdir.exists():
        tempdir.rmtree()
    tempdir.mkdir()

    bundle_zip = tempdir / 'bundle.zip'
    build_dir = tempdir / 'build'
    shell_execute('pip bundle -b {} {} {}'.format(build_dir, bundle_zip, '{}>=2013d'.format(package) if package == 'pytz' else package), capture=True, **kwargs)

    previous_cwd = os.getcwd()
    tempdir.chdir()
    if build_dir.exists():
        zipfile.ZipFile('bundle.zip').extract('pip-manifest.txt')
    else:
        # Older versions of pip delete the "build" directory after they
        # are done with it... So extract the entire bundle.zip
        zipfile.ZipFile('bundle.zip').extractall()

    downloaded_packages = {}
    for line in open('pip-manifest.txt'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        pkg_version = line.split('==')
        if len(pkg_version) != 2:
            bundle_file = os.path.abspath('pip-manifest.txt')
            raise ValueError('surprising line in %r: %r' % (bundle_file, line))
        pkg, version = pkg_version
        version = version.replace('-', '_')
        old_input_dir = os.path.join('build/', pkg)
        new_input_dir = '%s-%s' % (pkg, version)
        os.rename(old_input_dir, new_input_dir)
        output_name = os.path.join("..", new_input_dir + PACKAGE_SUFFIX)
        downloaded_packages[pkg] = (version, 'file://{}'.format(outdir / '{}{}'.format(new_input_dir, PACKAGE_SUFFIX)))
        shell_execute('tar czf {} {}'.format(output_name, new_input_dir), capture=True)

    os.chdir(previous_cwd)
    tempdir.rmtree()
    return downloaded_packages


def get_downloaded_python_package_version(name):
    versions = []
    OPT_PYPI = as_path('/opt/pypi')
    if OPT_PYPI.exists():
        prefix = '{}-'.format(name)
        for path in OPT_PYPI.files():
             filename = path.basename()
             if filename.startswith(prefix) and filename.endswith(PACKAGE_SUFFIX):
                versions.append((filename[len(prefix): -len(PACKAGE_SUFFIX)], 'file://{}'.format(path)))
        versions.sort(reverse=True)
    return versions[0] if versions else (None, None)
