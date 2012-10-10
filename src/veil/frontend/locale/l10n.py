from __future__ import unicode_literals, print_function, division
import babel.dates
import pytz
import datetime
from veil.frontend.template import template_filter
from veil.utility.clock import get_current_time
from .i18n import get_current_locale, _

DEFAULT_CLIENT_TIMEZONE = pytz.timezone('Asia/Shanghai')

@template_filter('timedelta')
def timedelta_filter(value):
    current_time = get_current_time()
    if current_time > value:
        delta = current_time - value
        direction = _(' ago')
    else:
        delta = value - current_time
        direction = _(' later')
    delta_str = babel.dates.format_timedelta(delta, locale=get_current_locale())
    return '{}{}'.format(delta_str, direction)


@template_filter('time')
def time_filter(value, format='medium'):
    return babel.dates.format_time(time=value, format=format, tzinfo=DEFAULT_CLIENT_TIMEZONE,
        locale=get_current_locale())


@template_filter('date')
def date_filter(value, format='medium'):
    return babel.dates.format_date(date=value, format=format, locale=get_current_locale())


@template_filter('datetime')
def datetime_filter(value, format='medium'):
    if 'epoch' == format:
        epoch = datetime.datetime.utcfromtimestamp(0).replace(tzinfo=pytz.utc)
        delta = value - epoch
        return delta.total_seconds()
    else:
        return babel.dates.format_datetime(datetime=value, format=format, tzinfo=DEFAULT_CLIENT_TIMEZONE,
            locale=get_current_locale())


def parse_epoch_datetime(text):
    if text:
        return datetime.datetime.utcfromtimestamp(float(text)).replace(tzinfo=pytz.utc)
    return None