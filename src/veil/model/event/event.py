from __future__ import unicode_literals, print_function, division
from logging import getLogger
from veil_component import *
from veil.model.collection import *

LOGGER = getLogger(__name__)
subscribers = {}

def define_event(topic):
    component_name = get_loading_component_name()
    if not component_name:
        raise Exception('event must be defined in component')
    record_dynamic_dependency_consumer(component_name, 'event', topic)
    return EventType(component_name=component_name, topic=topic)


def publish_event(event_type, loads_event_handlers=True, **kwargs):
    topic = get_topic(event_type)
    if loads_event_handlers:
        load_dynamic_dependency_providers('event', topic)
    if topic not in subscribers:
        return
    for subscriber in subscribers[topic]:
        try:
            subscriber(**kwargs)
        except:
            LOGGER.exception('failed to publish event: publishing topic %(topic)s to subscriber %(subscriber)s', {
                'topic': topic,
                'subscriber': subscriber
            })
            raise


def subscribe_event(event_type, subscriber):
    topic = get_topic(event_type)
    record_dynamic_dependency_provider(get_loading_component_name(), 'event', topic)
    subscribers.setdefault(topic, []).append(subscriber)


def unsubscribe_event(event_type, subscriber):
    topic = get_topic(event_type)
    topic_subscribers = subscribers.get(topic, [])
    if subscriber in topic_subscribers:
        topic_subscribers.remove(subscriber)


def event(event_type): #syntax sugar

    def decorator(subscriber):
        subscribe_event(event_type, subscriber)
        return subscriber

    return decorator


def get_topic(event_type):
    if not isinstance(event_type, EventType):
        raise Exception('is not of type EventType: {}'.format(event_type))
    return event_type.topic


class EventType(DictObject):
    def __init__(self, component_name, topic):
        super(EventType, self).__init__(component_name=component_name, topic=topic)

    def __repr__(self):
        return 'event:{}'.format(self.topic)