from __future__ import unicode_literals, print_function, division
from veil_component import load_dynamic_dependency_providers, record_dynamic_dependency_provider, get_loading_component_name
from veil.model.collection import *
from .case import test_hook
from .case import get_executing_test

fixtures = {}  # fixture_name => normally just the id of database record
fixture_providers = {}  # fixture_name => the provider function
fixture_types = {}  # type => reloaders


@test_hook
def reset_fixtures():
    get_executing_test().addCleanup(fixtures.clear)


def fixture(fixture_type, fixture_name):
    return FixtureProviderDecorator(fixture_type, fixture_name)


def delete_fixture_provider(fixture_name):
    del fixture_providers[fixture_name]


def get_fixture(fixture_name):
    return reload_fixture(fixture_providers[fixture_name].fixture_type, *fixtures[fixture_name])


def require_fixture(expected_fixture_type, fixture_name):
    load_dynamic_dependency_providers('fixture-type', expected_fixture_type)
    provider = fixture_providers[fixture_name]
    if expected_fixture_type != provider.fixture_type:
        raise Exception('{} is not {}'.format(fixture_name, expected_fixture_type))
    return provider()


class FixtureProviderDecorator(object):
    def __init__(self, fixture_type, fixture_name=None):
        self.fixture_type = fixture_type
        self.fixture_name = fixture_name

    def __call__(self, provider):
        record_dynamic_dependency_provider(get_loading_component_name(), 'fixture-type', self.fixture_type)
        return FixtureProvider(self.fixture_type, self.fixture_name or provider.__name__, provider)


class FixtureProvider(object):
    def __init__(self, fixture_type, fixture_name, provider):
        self.fixture_type = fixture_type
        self.fixture_name = fixture_name
        self.provider = provider
        if fixture_name in fixture_providers:
            raise Exception('duplicated fixture')
        else:
            fixture_providers[fixture_name] = self

    def __call__(self):
        if self.fixture_name not in fixtures:
            args = self.provider()
            fixtures[self.fixture_name] = args if isinstance(args, (list, tuple)) else [args]
        return get_fixture(self.fixture_name)


def reload_fixture(fixture_type, *reload_args):
    reloaders = fixture_types[fixture_type]
    fixture = {}
    for reloader in reloaders:
        fixture.update(reloader(*reload_args))
    fixture['e'] = lambda action_name, *args: fixture[action_name](*args)
    return objectify(fixture)


def fixture_reloader(fixture_type):
    def decorator(func):
        fixture_types.setdefault(fixture_type, []).append(func)
        return func

    return decorator
