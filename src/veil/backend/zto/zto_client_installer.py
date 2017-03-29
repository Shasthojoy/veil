from __future__ import unicode_literals, print_function, division
from veil.profile.installer import *

_config = {}

add_application_sub_resource('zto_client', lambda config: zto_client_resource(**config))


@composite_installer
def zto_client_resource(company_id, api_key, subscribe_create_by, subscribe_api_key):
    return [
        file_resource(path=VEIL_ETC_DIR / 'zto-client.cfg', content=render_config('zto-client.cfg.j2', company_id=company_id, api_key=api_key,
                                                                                  subscribe_create_by=subscribe_create_by, subscribe_api_key=subscribe_api_key))
    ]


def load_zto_client_config():
    return load_config_from(VEIL_ETC_DIR / 'zto-client.cfg', 'company_id', 'api_key', 'subscribe_create_by', 'subscribe_api_key')


def zto_client_config():
    global _config
    if not _config:
        _config = load_zto_client_config()
    return _config
