# -*- coding: utf-8 -*-

"""
支付宝新接口与旧接口对比：
    1. 不能依赖支付同步跳转判断支付是否成功，应以异步通知及主动查询为准
    2. 新接口使用RSA2签名方式
    3. 得到异步通知后，应使用支付宝提供的公钥进行验签, 'https://docs.open.alipay.com/291/106074/'
"""

from __future__ import unicode_literals, print_function, division

import base64
import json
import logging
import urllib
from decimal import Decimal
from decimal import DecimalException

import rsa

from veil.frontend.cli import *
from veil.profile.model import *
from veil.profile.web import *
from veil.utility.clock import *
from .alipay_client_installer import alipay_client_config

LOGGER = logging.getLogger(__name__)

NOTIFICATION_RECEIVED_SUCCESSFULLY_MARK = 'success'  # alipay require this 7 characters to be returned to them

PAYMENT_URL = 'https://openapi.alipay.com/gateway.do'
REQUEST_SUCCESS_CODE = '10000'

EVENT_ALIPAY_TRADE_PAID = define_event('alipay-trade-paid')


def create_alipay_pc_payment_url(out_trade_no, subject, body, total_amount, show_url, return_url, notify_url, minutes_to_expire):
    content_params = DictObject(out_trade_no=out_trade_no, subject=subject, body=body, total_amount='{:.2f}'.format(total_amount),
                                product_code='FAST_INSTANT_TRADE_PAY')

    # TODO: 签约新接口后，测试 'goods_detail'、'timeout_express' 字段
    # if show_url:
    #     content_params.goods_detail = json.dumps(dict(show_url=show_url), separators=(',', ':'))
    if minutes_to_expire:
        # content_params.timeout_express = '{}m'.format(100 or minutes_to_expire)
        content_params.timeout_express = '100m'
    return _create_alipay_payment_url('alipay.trade.page.pay', return_url, notify_url, content_params)


def create_alipay_wap_payment_url(out_trade_no, subject, body, total_amount, return_url, notify_url, minutes_to_expire):
    content_params = DictObject(out_trade_no=out_trade_no, subject=subject, body=body, total_amount='{:.2f}'.format(total_amount),
                                product_code='QUICK_WAP_WAY')
    if minutes_to_expire:
        content_params.timeout_express = '{}m'.format(minutes_to_expire)
    return _create_alipay_payment_url('alipay.trade.wap.pay', return_url, notify_url, content_params)


def _create_alipay_payment_url(method, return_url, notify_url, content_params):
    config = alipay_client_config()
    params = DictObject(
        app_id=config.app_id,
        method=method,
        charset='utf-8',
        timestamp=get_current_time_in_client_timezone().strftime('%Y-%m-%d %H:%M:%S'),
        return_url=return_url,
        notify_url=notify_url,
        biz_content=json.dumps(content_params, separators=(',', ':')),
        version='1.0',
        sign_type='RSA2'
    )
    params.sign = sign_rsa2(params, config.rsa2_private_key)
    return '{}?{}'.format(PAYMENT_URL, urlencode(params))


def make_alipay_app_payment_order_str(out_trade_no, subject, body, total_amount, notify_url, minutes_to_expire):
    config = alipay_client_config()
    content_params = DictObject(out_trade_no=out_trade_no, subject=subject, body=body, total_amount='{:.2f}'.format(total_amount),
                                product_code='QUICK_MSECURITY_PAY')
    if minutes_to_expire:
        content_params.timeout_express = '{}m'.format(minutes_to_expire)
    params = DictObject(
        app_id=config.app_id,
        method='alipay.trade.app.pay',
        charset='utf-8',
        timestamp=get_current_time_in_client_timezone().strftime('%Y-%m-%d %H:%M:%S'),
        notify_url=notify_url,
        biz_content=json.dumps(content_params, separators=(',', ':')),
        version='1.0',
        sign_type='RSA2'
    )
    message = '&'.join('{}={}'.format(key, urllib.quote(params[key])) for key in params if params[key])
    return '{}&sign={}'.format(message, urllib.quote(sign_rsa2(params, config.rsa2_private_key)))


def mark_alipay_payment_successful(out_trade_no, arguments, is_async_result=True):
    if is_async_result:
        if validate_notification_arguments(arguments):
            LOGGER.info('alipay notify verify SUCCESS: %(out_trade_no)s, %(arguments)s', {'out_trade_no': out_trade_no, 'arguments': arguments})
        else:
            LOGGER.warn('alipay notify verify ERROR: %(out_trade_no)s, %(arguments)s', {'out_trade_no': out_trade_no, 'arguments': arguments})
            return

    trade_no, buyer_id, total_amount, paid_at, discarded_reasons = parse_alipay_payment_return_arguments(out_trade_no, arguments, is_async_result)
    if discarded_reasons:
        LOGGER.error('alipay trade notification discarded: %(discarded_reasons)s, %(arguments)s', {
            'discarded_reasons': discarded_reasons,
            'arguments': arguments
        })
        set_http_status_code(httplib.BAD_REQUEST)
        return '<br/>'.join(discarded_reasons)
    else:
        publish_event(EVENT_ALIPAY_TRADE_PAID, out_trade_no=out_trade_no, payment_channel_trade_no=arguments.trade_no, payment_channel_buyer_id=buyer_id,
                      paid_total=total_amount, paid_at=paid_at)
        return NOTIFICATION_RECEIVED_SUCCESSFULLY_MARK


def validate_notification_arguments(arguments):
    sign = arguments.pop('sign', None)
    sign_type = arguments.pop('sign_type', None)
    if not sign or not sign_type:
        return False

    message = to_url_params_string(arguments)
    config = alipay_client_config()
    try:
        verify_rsa(message.encode('UTF-8'), base64.b64decode(sign), config.alipay_rsa2_public_key)
    except:
        return False
    else:
        return True


def parse_alipay_payment_return_arguments(out_trade_no, arguments, is_async_result=True):
    discarded_reasons = []
    if is_async_result:  # 支付宝查询接口同步返回的信息没有 'app_id'
        app_id = arguments.get('app_id')
        if not app_id:
            discarded_reasons.append('no app_id')
        elif app_id != alipay_client_config().app_id:
            discarded_reasons.append('app_id mismatched')
    if arguments.get('trade_status') not in {'TRADE_SUCCESS', 'TRADE_FINISHED'}:
        discarded_reasons.append('trade not succeeded')
    out_trade_no_ = arguments.get('out_trade_no')
    if not out_trade_no_:
        discarded_reasons.append('no out_trade_no')
    elif out_trade_no_ != out_trade_no:
        discarded_reasons.append('inconsistent out_trade_no: expected={}, actual={}'.format(out_trade_no, out_trade_no_))
    trade_no = arguments.get('trade_no')
    if not trade_no:
        discarded_reasons.append('no trade_no')
    total_amount = arguments.get('total_amount')
    if total_amount:
        try:
            total_amount = Decimal(total_amount)
        except DecimalException:
            discarded_reasons.append('invalid total_amount: {}'.format(total_amount))
    else:
        discarded_reasons.append('no total_amount')
    paid_at = arguments.get('gmt_payment') or arguments.get('notify_time') or arguments.get('send_pay_date')  # 买家付款时间，时区为GMT+8 beijing，格式为 yyyy-MM-dd HH:mm:ss
    if paid_at:
        try:
            paid_at = to_datetime(format='%Y-%m-%d %H:%M:%S')(paid_at)
        except Exception:
            discarded_reasons.append('invalid gmt_payment or notify_time: {}'.format(paid_at))
    else:
        discarded_reasons.append('no gmt_payment or notify_time')
    return trade_no, arguments.get('buyer_logon_id') or arguments.get('buyer_id'), total_amount, paid_at, discarded_reasons


@script('query-alipay-status')
def query_alipay_payment_status_script(out_trade_no):
    query_alipay_payment_status(out_trade_no)


def query_alipay_payment_status(out_trade_no):
    config = alipay_client_config()
    params = DictObject(
        app_id=config.app_id,
        method='alipay.trade.query',
        charset='utf-8',
        timestamp=get_current_time_in_client_timezone().strftime('%Y-%m-%d %H:%M:%S'),
        biz_content=json.dumps(dict(out_trade_no=out_trade_no), separators=(',', ':')),
        version='1.0',
        sign_type='RSA2'
    )
    params.sign = sign_rsa2(params, config.rsa2_private_key)
    try:
        response = requests.get(PAYMENT_URL, params=params, timeout=(3.05, 9), max_retries=Retry(total=3, backoff_factor=0.2))
        response.raise_for_status()
    except Exception:
        LOGGER.exception('alipay payment query exception-thrown: %(params)s', {'params': params})
        raise
    else:
        LOGGER.debug(response.content)
        content = from_json(response.content)
        arguments = DictObject(content['alipay_trade_query_response'])
        arguments.sign = content['sign']
        if arguments.code == REQUEST_SUCCESS_CODE:
            result = mark_alipay_payment_successful(out_trade_no, arguments, is_async_result=False)
            paid = result == NOTIFICATION_RECEIVED_SUCCESSFULLY_MARK
        else:
            LOGGER.error('alipay payment query failed: %(out_trade_no)s, %(code)s, %(msg)s, %(sub_code)s, %(sub_msg)s, %(params)s, %(arguments)s',
                         {'out_trade_no': out_trade_no, 'code': arguments.code, 'msg': arguments.msg, 'sub_code': arguments.sub_code,
                          'sub_msg': arguments.sub_msg, 'params': params, 'arguments': arguments})
            paid = False
    return paid


@script('close-alipay-payment-trade')
def close_alipay_payment_trade_script(out_trade_no):
    close_alipay_payment_trade(out_trade_no)


def close_alipay_payment_trade(out_trade_no, notify_url=None):
    config = alipay_client_config()
    params = DictObject(
        app_id=config.app_id,
        method='alipay.trade.close',
        charset='utf-8',
        timestamp=get_current_time_in_client_timezone().strftime('%Y-%m-%d %H:%M:%S'),
        biz_content=json.dumps(dict(out_trade_no=out_trade_no), separators=(',', ':')),
        notify_url=notify_url,
        version='1.0',
        sign_type='RSA2'
    )
    params.sign = sign_rsa2(params, config.rsa2_private_key)
    try:
        response = requests.get(PAYMENT_URL, params=params, timeout=(3.05, 9), max_retries=Retry(total=3, backoff_factor=0.2))
        response.raise_for_status()
    except Exception:
        LOGGER.exception('alipay payment query exception-thrown: %(params)s', {'params': params})
        raise
    else:
        LOGGER.debug(response.content)
        content = from_json(response.content)
        arguments = DictObject(content['alipay_trade_close_response'])
        arguments.sign = content['sign']
        if arguments.code == REQUEST_SUCCESS_CODE:
            LOGGER.info('requst alipay payment close success: %(out_trade_no)s, %(params)s, %(arguments)s',
                        {'out_trade_no': out_trade_no, 'params': params, 'arguments': arguments})
        else:
            LOGGER.error('request alipay payment close failed: %(out_trade_no)s, %(code)s, %(msg)s, %(sub_code)s, %(sub_msg)s, %(params)s, %(arguments)s',
                         {'out_trade_no': out_trade_no, 'code': arguments.code, 'msg': arguments.msg, 'sub_code': arguments.sub_code,
                          'sub_msg': arguments.sub_msg, 'params': params, 'arguments': arguments})


def sign_rsa2(params, keyfile_path):
    with open(keyfile_path) as f:
        private_key = rsa.PrivateKey.load_pkcs1(f.read())
    return base64.b64encode(rsa.sign(to_url_params_string(params).encode('UTF-8'), private_key, 'SHA-256'))


def to_url_params_string(params):
    return '&'.join('{}={}'.format(key, params[key]) for key in sorted(params) if params[key])


def verify_rsa(message, sign, public_key_path):
    with open(public_key_path) as f:
        public_key = rsa.PublicKey.load_pkcs1_openssl_pem(f.read())
    try:
        rsa.verify(message, sign, public_key)
    except rsa.VerificationError:
        raise Exception('verify failed')
