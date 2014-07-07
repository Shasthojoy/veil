# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, division
from veil.environment.environment import *
from veil.server.config import *
from veil.utility.shell import *
from veil_installer import *

KIBANA_DIR = OPT_DIR / 'kibana-latest'


@composite_installer
def kibana_resource(config):
    if not (OPT_DIR / 'kibana-latest.zip').exists():
        shell_execute('wget http://download.elasticsearch.org/kibana/kibana/kibana-latest.zip', cwd=OPT_DIR)
    if not KIBANA_DIR.exists():
        shell_execute('unzip kibana-latest.zip', cwd=OPT_DIR)
        if (KIBANA_DIR / 'app/dashboards/logstash.json').exists():
            shell_execute('mv {} default.json'.format(KIBANA_DIR / 'app/dashboards/logstash.json'))
    resources = [
        os_ppa_repository_resource(name='nginx/stable'),
        os_package_resource(name='nginx-extras'),
        os_service_resource(state='not_installed', name='nginx'),
        file_resource(path=VEIL_ETC_DIR / 'nginx.conf', content=render_config('nginx.conf.j2', kibana_root=KIBANA_DIR)),
        file_resource(path=KIBANA_DIR / 'config.js', content=render_config('kibana.config.js.j2', **config))
    ]

    return resources