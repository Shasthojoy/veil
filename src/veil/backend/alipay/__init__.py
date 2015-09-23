import veil_component

with veil_component.init_component(__name__):
    from .alipay_payment import EVENT_ALIPAY_TRADE_PAID
    from .alipay_payment import NOTIFIED_FROM_RETURN_URL
    from .alipay_payment import NOTIFIED_FROM_NOTIFY_URL
    from .alipay_payment import create_alipay_payment_url
    from .alipay_payment import process_alipay_payment_notification
    from .alipay_payment import query_alipay_payment_status
    from .alipay_payment import create_alipay_mobile_message
    from .alipay_payment import verify_alipay_sync_notification

    from .alipay_client_installer import alipay_client_resource

    __all__ = [
        'EVENT_ALIPAY_TRADE_PAID',
        'NOTIFIED_FROM_RETURN_URL',
        'NOTIFIED_FROM_NOTIFY_URL',
        create_alipay_payment_url.__name__,
        process_alipay_payment_notification.__name__,
        query_alipay_payment_status.__name__,
        create_alipay_mobile_message.__name__,
        verify_alipay_sync_notification.__name__,

        alipay_client_resource.__name__,
    ]
