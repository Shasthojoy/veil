######## export begin
from .command import command
from .command import command_for
from .command import InvalidCommand
from .command import CommandError
from .command import NotFoundError
from ._test import command_fixture
from ._test import test_object_provider

__all__ = [
    # from command
    command.__name__,
    command_for.__name__,
    InvalidCommand.__name__,
    CommandError.__name__,
    NotFoundError.__name__,
    # from fixture
    command_fixture.__name__,
    test_object_provider.__name__
]
######## export end

def init():
    from sandal.component import init_component

    init_component(__name__)

init()