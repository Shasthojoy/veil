import veil_component

with veil_component.init_component(__name__):
    from .browser import start_website_and_browser
    from .browser import load_page_interactions

    __all__ = [
        start_website_and_browser.__name__,
        load_page_interactions.__name__
    ]

    def init():
        from veil.environment import VEIL_ENV
        if 'test' == VEIL_ENV:
            from veil.environment.setting import add_settings
            from .browser_test import TEST_WEBSITE_SETTINGS

            add_settings(TEST_WEBSITE_SETTINGS)