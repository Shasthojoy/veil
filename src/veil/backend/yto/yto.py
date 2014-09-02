# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, division
import logging
import base64
import re
from hashlib import md5
from veil.model.collection import *
from veil.utility.http import *
from veil.utility.encoding import *
from .yto_client_installer import yto_client_config

LOGGER = logging.getLogger(__name__)

YTO_SIGNED_STATUS = 'SIGNED'
YTO_SIGNED_FAILED_STATUS = 'FAILED'
YTO_REJECTED_REMARK = '收方客户拒收'
YTO_STATUS = {
    'GOT': '揽收成功',
    'NOT_SEND': '揽收失败',
    'SENT_SCAN': '派件扫描',
    YTO_SIGNED_STATUS: '签收成功',
    YTO_SIGNED_FAILED_STATUS: '签收失败'
}


def verify_request(data, sign):
    config = yto_client_config()
    return sign == base64.b64encode(md5(to_str('{}{}'.format(data, config.partner_id))).digest())


def get_brief(status_obj):
    element_remark = status_obj.find('remark')
    if status_obj.infoContent.text == 'SENT_SCAN':
        return '：'.join(e for e in [YTO_STATUS['SENT_SCAN'], element_remark.text if element_remark else None] if e)
    elif is_rejected_response(status_obj):
        return '{} 原因：{}'.format(YTO_STATUS[YTO_SIGNED_FAILED_STATUS], element_remark.text if element_remark else '-')
    elif status_obj.infoContent.text == YTO_SIGNED_STATUS:
        name_element = status_obj.find('name')
        result = '{} 签收人：{}'.format(YTO_STATUS[YTO_SIGNED_STATUS], name_element.text if name_element else '-')
        if element_remark:
            return '{} ({})'.format(result, element_remark.text)
        return result
    else:
        return YTO_STATUS.get(status_obj.infoContent.text)


def get_signed_name_and_signed_failed_reason(status_obj):
    name = status_obj.find('name')
    name = name.text if name else None
    reason = status_obj.find('remark')
    reason = reason.text if reason else None
    return name, reason


def get_logistics_status(status_obj):
    code = status_obj.infoContent.text
    if code in (YTO_SIGNED_FAILED_STATUS, YTO_SIGNED_STATUS):
        is_rejected = is_rejected_response(status_obj)
        if is_rejected:
            code = YTO_SIGNED_FAILED_STATUS
        name, reason = get_signed_name_and_signed_failed_reason(status_obj)
        return DictObject(code=code, brief=get_brief(status_obj), signed_name=name, signed_failed_reason=reason, is_rejected=is_rejected)
    return DictObject(code=code, brief=get_brief(status_obj))


def is_rejected_response(status_obj):
    if status_obj.infoContent.text == YTO_SIGNED_FAILED_STATUS and status_obj.remark.text == YTO_REJECTED_REMARK:
        return True
    if status_obj.infoContent.text != YTO_SIGNED_STATUS:
        return False
    name_element = status_obj.find('name')
    if name_element and '退' in name_element.text:
        if name_element.text.startswith('退'):
            return True
        else:
            logistics_no = status_obj.txLogisticID.text
            LOGGER.info('maybe new pattern of reject: %(logistics_no)s, %(name)s', {
                'logistics_no': logistics_no, 'name': name_element.text
            })
    return False


def subscribe(purchase_id, purchase_xml_data):
    config = yto_client_config()
    purchase_data_digest = base64.b64encode(md5(to_str('{}{}'.format(purchase_xml_data, config.partner_id))).digest())
    data = {
        'logistics_interface': to_str(purchase_xml_data),
        'data_digest': purchase_data_digest,
        'type': config.type,
        'clientId': config.client_id
    }
    response = to_unicode(http_call('Subscribe-purchases-logistics-status', config.api_url, data=data,
        content_type='application/x-www-form-urlencoded; charset=UTF-8'))
    if '<success>false</success>' in response:
        reason = re.findall('<reason>(.*)</reason>', response)[0]
        LOGGER.info('Failed subscribe purchases logistics status: %(purchase_id)s, %(reason)s', {'purchase_id': purchase_id, 'reason': reason})
        raise SubscribeLogisticsStatusException('Failed subscribe purchases logistics status: {} {}'.format(purchase_id, reason))
    elif '<success>true</success>' in response:
        LOGGER.info('Subscribe purchases logistics status successfully: %(purchase_id)s', {'purchase_id': purchase_id})
        return True
    else:
        LOGGER.info('Get error response from yto: %(response)s', {'response': response})
    return False


class SubscribeLogisticsStatusException(Exception):
    pass