# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, division

import zlib
import gzip
import logging
from cStringIO import StringIO
from random import randint
from hashlib import md5
from base64 import b64encode, b64decode

from decimal import Decimal

from veil.backend.web_service import *
from veil.environment import VEIL_BUCKET_LOG_DIR
from veil.frontend.template import *
from veil.model.collection import *
from veil.utility.clock import *
from veil.utility.encoding import *
from veil.utility.misc import *
from veil.utility.xml import *
from veil_component import VEIL_ENV_TYPE

LOGGER = logging.getLogger(__name__)

REQUEST_AND_RESPONSE_LOG_DIRECTORY_BASE = VEIL_BUCKET_LOG_DIR / 'aisino'

if VEIL_ENV_TYPE == 'public':
    url = ''
else:
    url = 'http://ei-test.51fapiao.cn:20080/51TransferServicePro_zzs/webservice/eInvWS?wsdl'

INVOICE_INTERFACE_NAME_FOR_INVOICE = 'ECXML.FPKJ.BC.E_INV'
INVOICE_INTERFACE_NAME_FOR_DOWNLOAD = 'ECXML.FPXZ.CX.E_INV'
INVOICE_APP_ID_NORMAL = 'DZFP'
INVOICE_APP_ID_VAT = 'ZZS_PT_DZFP'
INVOICE_TYPE_CODE_NORMAL = '1'
INVOICE_TYPE_CODE_RED = '2'
INVOICE_BUYER_TYPE_COMPANY = '01'
INVOICE_BUYER_TYPE_GOV = '02'
INVOICE_BUYER_TYPE_PERSONAL = '03'
INVOICE_BUYER_TYPE_OTHER = '04'
INVOICE_ITEM_TYPE_NORMAL = 0
INVOICE_ITEM_TYPE_DISCOUNT = 1
INVOICE_ITEM_TYPE_BE_DISCOUNTED = 2
INVOICE_OPERATION_CODE_NORMAL = 10
INVOICE_OPERATION_CODE_REVERT_NORMAL = 11
INVOICE_OPERATION_CODE_RETURN_RED = 20
INVOICE_OPERATION_CODE_REVERT_RED = 21
INVOICE_OPERATION_CODE_REPLACE_RED = 22
DATA_GZIP_COMPRESSED = '1'
CONTENT_DATA_ENCRYPT_CODE_NO = '0'
CONTENT_DATA_ENCRYPT_CODE_CA = '2'
SUPPORTED_ENCRYPT_CODES = {CONTENT_DATA_ENCRYPT_CODE_NO, CONTENT_DATA_ENCRYPT_CODE_CA}
DEFAULT_TAX_RATE = Decimal('0.17')
RESPONSE_SUCCESS_MARK = '0000'
RESPONSE_QUERY_SUCCESS_MARK = '3000'
REQUEST_SEQ_LENGTH = 20
DOWNLOAD_METHOD_FOR_QUERY = '0'
DOWNLOAD_METHOD_FOR_DOWNLOAD = '1'
RED_INVOICE_FLAG_NORMAL = '0'
RED_INVOICE_FLAG_SPECIAL = '1'


def request_invoice(request_seq, ebp_code, registration_no, username, buyer, tax_payer, operator_name, invoice_content, total, items,
                    ref_invoice_code=None, ref_invoice_no=None, comment=None, operation_code=INVOICE_OPERATION_CODE_NORMAL,
                    flag_special_red=None, red_invoice_reason=None,
                    terminal_code=0, app_id=INVOICE_APP_ID_VAT, version='2.0', response_code=144, encrypt_code=2, encrypt_code_type='CA', sample_code='000001',
                    encode_table_version='1.0', flag_dk=0, flag_list=0, list_item_name=None, without_tax_total=0, tax_total=0):

    type_code = INVOICE_TYPE_CODE_NORMAL if total > 0 else INVOICE_TYPE_CODE_RED

    if type_code == INVOICE_TYPE_CODE_NORMAL and (ref_invoice_code is not None or ref_invoice_no is not None):
        raise Exception('正票发票不允许提供原发票代码和号码')
    if type_code == INVOICE_TYPE_CODE_RED and (ref_invoice_code is None or ref_invoice_no is None):
        raise Exception('冲红发票必须提供原发票代码和号码')
    if flag_special_red is not None and flag_special_red not in {RED_INVOICE_FLAG_NORMAL, RED_INVOICE_FLAG_SPECIAL}:
        raise Exception('特殊冲红标志只能为0：正常冲红或1：冲纸质票等')
    if type_code == INVOICE_TYPE_CODE_RED and flag_special_red is None:
        raise Exception('冲红时特殊冲红标志不能为空')
    if flag_list is not None and flag_list not in {0, 1}:
        raise Exception('清单选项只能为0或1')
    if flag_list == 1 and list_item_name is None:
        raise Exception('请填写清单项目名称')

    if app_id == INVOICE_APP_ID_VAT and type_code == INVOICE_TYPE_CODE_RED:
        comment = '对应正数发票代码:{} 号码:{}'.format(ref_invoice_code, ref_invoice_no)

    with require_current_template_directory_relative_to():
        interface_content = get_template('invoice.xml').render(request_seq=request_seq, ebp_code=ebp_code, buyer=buyer, tax_payer=tax_payer,
                                                               sample_code=sample_code, encode_table_version=encode_table_version, operator_name=operator_name,
                                                               invoice_content=invoice_content, total=total, items=items, without_tax_total=without_tax_total,
                                                               tax_total=tax_total, type_code=type_code,
                                                               ref_invoice_code=ref_invoice_code, ref_invoice_no=ref_invoice_no, comment=comment,
                                                               flag_dk=flag_dk, red_invoice_reason=red_invoice_reason, flag_special_red=flag_special_red,
                                                               INVOICE_TYPE_CODE_RED=INVOICE_TYPE_CODE_RED, operation_code=operation_code, flag_list=flag_list,
                                                               list_item_name=list_item_name)
    interface_content = b64encode(get_compressed_content(get_ca_encrypted_content(to_str(interface_content))))
    with require_current_template_directory_relative_to():
        interface_data = get_template('interface.xml').render(terminal_code=terminal_code, app_id=app_id, version=version, response_code=response_code,
                                                              interface_name=INVOICE_INTERFACE_NAME_FOR_INVOICE, username=username,
                                                              password=generate_request_password(registration_no),
                                                              tax_payer=tax_payer, request_code=ebp_code,
                                                              request_time=get_request_time(), ebp_code=ebp_code,
                                                              data_exchange_id=generate_data_exchange_id(ebp_code), is_compressed=True,
                                                              encrypt_code=encrypt_code, encrypt_code_type=encrypt_code_type,
                                                              interface_content=interface_content)
    ws = WebService(url)
    try:
        response = ws.eiInterface(interface_data)
    except Exception as e:
        LOGGER.info('failed request invoice: %(request_seq)s, %(message)s', {'request_seq': request_seq, 'message': e.message})
        raise
    finally:
        record_request_and_response(ws, 'FPKJ', request_seq)
    response_obj = parse_xml(to_str(response))
    response_obj.returnStateInfo.is_success = response_obj.returnStateInfo.returnCode == RESPONSE_SUCCESS_MARK
    return response_obj.returnStateInfo


def decrypt_content_data(data):
    if data.dataDescription.encryptCode not in SUPPORTED_ENCRYPT_CODES:
        raise Exception('not support encrypt code: {}'.format(data.dataDescription.encryptCode))
    if data.dataDescription.encryptCode == CONTENT_DATA_ENCRYPT_CODE_CA:
        # decrypt by CA
        data.content = ''


def get_ca_encrypted_content(raw_content):
    # TODO: waiting for shared library
    return raw_content


def get_compressed_content(content):
    buf = StringIO()
    with gzip.GzipFile(mode='wb', fileobj=buf) as f:
        f.write(content)
    return buf.getvalue()


def generate_request_password(registration_no):
    return '{}{}'.format(str(randint(0, 9999999999)).zfill(10), b64encode(md5('{}{}'.format(str(randint(0, 9999999999)).zfill(10), registration_no)).digest()))


def generate_data_exchange_id(request_code):
    return '{}{}'.format(request_code, get_current_time_in_client_timezone().strftime('%Y%m%d%H%M%S%f')[:-3])


def get_request_time():
    return get_current_time().strftime('%Y-%m-%d %H:%M:%S %f')[:-3]


def download_invoice(request_seq, ebp_code, registration_no, username, tax_payer, download_method=DOWNLOAD_METHOD_FOR_DOWNLOAD,
                     terminal_code=0, app_id=INVOICE_APP_ID_VAT, version='2.0', response_code=144, encrypt_code=2, encrypt_code_type='CA'):
    with require_current_template_directory_relative_to():
        interface_content = get_template('download.xml').render(request_seq=request_seq, ebp_code=ebp_code, tax_payer=tax_payer,
                                                                download_method=download_method)
    interface_content = b64encode(get_compressed_content(get_ca_encrypted_content(to_str(interface_content))))
    with require_current_template_directory_relative_to():
        interface_data = get_template('interface.xml').render(terminal_code=terminal_code, app_id=app_id, version=version, response_code=response_code,
                                                              interface_name=INVOICE_INTERFACE_NAME_FOR_DOWNLOAD, username=username,
                                                              password=generate_request_password(registration_no),
                                                              tax_payer=tax_payer, request_code=ebp_code,
                                                              request_time=get_request_time(), ebp_code=ebp_code,
                                                              data_exchange_id=generate_data_exchange_id(ebp_code), is_compressed=False,
                                                              encrypt_code=encrypt_code, encrypt_code_type=encrypt_code_type,
                                                              interface_content=interface_content)
    ws = WebService(url)
    try:
        response = ws.eiInterface(interface_data)
    except Exception as e:
        LOGGER.info('failed request invoice: %(request_seq)s, %(message)s', {'request_seq': request_seq, 'message': e.message})
        raise
    finally:
        record_request_and_response(ws, 'FPXZ' if download_method == DOWNLOAD_METHOD_FOR_DOWNLOAD else 'FPCX', request_seq)
    response_obj = parse_xml(to_str(response))

    if download_method == DOWNLOAD_METHOD_FOR_DOWNLOAD:
        decode_content_data(response_obj.Data)
        uncompress_content_data(response_obj.Data)
        decrypt_content_data(response_obj.Data)
        parse_content_data(response_obj.Data)

    if download_method == DOWNLOAD_METHOD_FOR_DOWNLOAD and response_obj.returnStateInfo.returnCode == RESPONSE_SUCCESS_MARK:
        response_obj.is_success = True
    elif download_method == DOWNLOAD_METHOD_FOR_QUERY and response_obj.returnStateInfo.returnCode == RESPONSE_QUERY_SUCCESS_MARK:
        response_obj.is_success = True
    else:
        response_obj.is_success = False

    return response_obj


def query_invoice(request_seq, ebp_code, registration_no, username, tax_payer,
                  terminal_code=0, app_id=INVOICE_APP_ID_VAT, version='2.0', response_code=144, encrypt_code=2, encrypt_code_type='CA'):
    return download_invoice(request_seq, ebp_code, registration_no, username, tax_payer, download_method=DOWNLOAD_METHOD_FOR_QUERY,
                            terminal_code=terminal_code, app_id=app_id, version=version, response_code=response_code, encrypt_code=encrypt_code,
                            encrypt_code_type=encrypt_code_type)


def uncompress_content_data(data):
    if data.dataDescription.zipCode == DATA_GZIP_COMPRESSED:
        data.content = zlib.decompress(data.content, zlib.MAX_WBITS | 16)


def decode_content_data(data):
    data.content = b64decode(data.content)


def parse_content_data(data):
    data.content = parse_xml(data.content)
    data.without_file_content = {k: v for k, v in data.content.items() if k != 'PDF_FILE'}
    data.content.PDF_FILE = StringIO(b64decode(data.content.PDF_FILE))


def as_request_seq(request_id):
    # TODO : remove test seq generator code
    return 'LJBBTEST' + str(randint(0, 999)).zfill(3) + str(request_id).zfill(REQUEST_SEQ_LENGTH-len('LJBBTEST') - 3)
    return str(request_id).zfill(REQUEST_SEQ_LENGTH)


class InvoiceBuyer(DictObject):
    def __init__(self, type, id, name, mobile, telephone, address, bank_name, bank_account_no):
        super(InvoiceBuyer, self).__init__()
        self.type = type
        self.id = id
        if self.type == INVOICE_BUYER_TYPE_PERSONAL:
            if name:
                self.name = '个人({})'.format(name)
            else:
                self.name = '个人'
        else:
            self.name = name
        self.mobile = mobile
        self.telephone = telephone
        self.address = address
        self.bank_name = bank_name
        self.bank_account_no = bank_account_no


class InvoiceTaxPayer(DictObject):
    def __init__(self, id, name, auth_code, address, telephone, bank_name, bank_account_no):
        super(InvoiceTaxPayer, self).__init__()
        self.id = id
        self.name = name
        self.auth_code = auth_code
        self.address = address
        self.telephone = telephone
        self.bank_name = bank_name
        self.bank_account_no = bank_account_no


class InvoiceItem(DictObject):
    def __init__(self, type, code, name, quantity, total, tax_rate=DEFAULT_TAX_RATE, with_tax=True, with_promotion=True):
        super(InvoiceItem, self).__init__()
        self.type = type
        self.code = code
        self.name = name
        self.quantity = quantity
        self.total = Decimal(total)
        self.price = self.total / self.quantity
        self.tax_rate = tax_rate
        self.tax_total = round_money_ceiling(self.total * self.tax_rate)
        self.with_tax = with_tax
        self.with_promotion = with_promotion


def record_request_and_response(ws, interface_name, request_seq):
    current_time_string = get_current_time_in_client_timezone().strftime('%Y%m%d%H%M%S')
    log_file_dir = REQUEST_AND_RESPONSE_LOG_DIRECTORY_BASE / current_time_string[:4] / current_time_string[4:6]
    log_file_dir.makedirs()
    request_log_file_name = '{}-{}-{}-req.xml'.format(current_time_string, request_seq, interface_name)
    response_log_file_name = '{}-{}-{}-rsp.xml'.format(current_time_string, request_seq, interface_name)
    with open(log_file_dir / request_log_file_name, mode='wb+') as f:
        f.write(ws.last_sent())
    with open(log_file_dir / response_log_file_name, mode='wb+') as f:
        f.write(ws.last_received())
