from __future__ import unicode_literals, print_function, division
from veil_installer import *
from veil.frontend.template import *
from veil.model.collection import *
from veil.environment import *
from veil.environment.setting import *
from veil.development.test import *

overridden_bucket_configs = {}

@composite_installer('bucket')
@using_isolated_template
def install_bucket(purpose, config):
    resources = list(BASIC_LAYOUT_RESOURCES)
    resources.append(
        file_resource(VEIL_ETC_DIR / '{}-bucket.cfg'.format(purpose.replace('_', '-')), content=get_template(
            'bucket.cfg.j2').render(config=config)))
    return [], resources


def override_bucket_config(purpose, **overrides):
    get_executing_test().addCleanup(overridden_bucket_configs.clear)
    overridden_bucket_configs.setdefault(purpose, {}).update(overrides)


def load_bucket_config(purpose):
    if 'test' == VEIL_SERVER:
        try:
            config = load_config_from(VEIL_ETC_DIR / '{}-bucket.cfg'.format(purpose.replace('_', '-')),
                'type', 'base_directory', 'base_url')
        except IOError, e:
            config = DictObject()
        config.update(overridden_bucket_configs.get(purpose, {}))
        return config
    else:
        return load_config_from(VEIL_ETC_DIR / '{}-bucket.cfg'.format(purpose.replace('_', '-')),
            'type', 'base_directory', 'base_url')
