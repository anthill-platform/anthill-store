from tornado.gen import coroutine, Return
from tornado.httpclient import AsyncHTTPClient, HTTPRequest, HTTPError

from . import StoreComponent, StoreComponents, StoreComponentError

from ..order import OrdersModel, OrderError

from common import to_int
from common.access import parse_account
from common.social import APIError
from common.internal import Internal, InternalError

import logging

import urllib
import ujson
import hashlib


class MailRuStoreComponent(StoreComponent):

    def __init__(self):
        super(MailRuStoreComponent, self).__init__()
        self.internal = Internal()

        self.client = AsyncHTTPClient()

    def is_hook_applicable(self):
        return True

    @coroutine
    def update_order(self, app, gamespace_id, account_id, order, order_info):

        if order.status != OrdersModel.STATUS_APPROVED:
            raise StoreComponentError(409, "Order is not approved")

        result = (OrdersModel.STATUS_SUCCEEDED, {})
        raise Return(result)

    @coroutine
    def order_callback(self, app, gamespace_id, store_id, arguments, headers, body_str):

        try:
            uid = arguments["uid"]
            sum_str = arguments["sum"]
            merchant_param_str = arguments["merchant_param"]
            sign = arguments["sign"]
            tid = arguments["tid"]
        except KeyError:
            raise Return({
                "status": "error",
                "errcode": 400,
                "errmsg": "Missing argument(s)"
            })

        try:
            sum = float(sum_str)
        except ValueError:
            raise Return({
                "status": "error",
                "errcode": 400,
                "errmsg": "Bad sum"
            })

        sum_cents = int(sum * 100)

        try:
            merchant_param = ujson.loads(merchant_param_str)
        except (KeyError, ValueError):
            raise Return({
                "status": "error",
                "errcode": 400,
                "errmsg": "Corrupted merchant_param"
            })

        try:
            order_id = merchant_param["order_id"]
            item_id = merchant_param["item_id"]
        except KeyError:
            raise Return({
                "status": "error",
                "errcode": 400,
                "errmsg": "Missing argument(s)"
            })

        mailru_api = app.mailru_api
        private_key = yield mailru_api.get_private_key(gamespace_id)

        expected_sign = mailru_api.calculate_signature({
            "merchant_param": merchant_param_str,
            "sum": sum_str,
            "tid": tid,
            "uid": uid
        }, private_key)

        if expected_sign != sign:
            raise Return({
                "status": "error",
                "errcode": 403,
                "errmsg": "Invalid signature"
            })

        logging.info("__notification_payment__: {0} {1} {2} {3}".format(
            gamespace_id, store_id, ujson.dumps(arguments), ujson.dumps(headers)))

        orders = app.orders

        try:
            result = yield orders.update_order_status_reliable(
                gamespace_id, order_id, OrdersModel.STATUS_CREATED, OrdersModel.STATUS_APPROVED,
                {
                    "transaction_id": tid
                }, ensure_order_total=sum_cents, ensure_item_id=item_id)
        except OrderError as e:
            raise Return({
                "status": "error",
                "errcode": e.code,
                "errmsg": e.message
            })

        if not result:
            raise Return({
                "status": "error",
                "errcode": 409,
                "errmsg": "transaction is in wrong state, cannot approve"
            })

        raise Return({
            "status": "ok"
        })

    @coroutine
    def __get_account_uid__(self, account_id):
        """
        Returns mailru's credential (mailru:xxxxxxx) for account id if there's one
        :param account_id:
        :return:
        """

        try:
            result = yield self.internal.request(
                "login", "get_credential",
                credential_type="mailru", account_id=str(account_id))
        except InternalError as e:
            if e.code == 404:
                raise Return(None)

            raise StoreComponentError(500, e.message)

        raise Return(result.get("credential", None))

    @coroutine
    def new_order(self, app, gamespace_id, account_id, order_id, currency,
                  price, amount, total, store, item, env, campaign_item):

        mailru_api = app.mailru_api

        private_key = yield mailru_api.get_private_key(gamespace_id)

        uid = yield self.__get_account_uid__(account_id)

        if not uid:
            raise StoreComponentError(406, "No credential of type 'mailru' is associated with this account.")

        uid_parsed = parse_account(uid)

        if not uid_parsed:
            raise StoreComponentError(406, "No credential of type 'mailru' is associated with this account.")

        try:
            ip_address = env["ip_address"]
        except KeyError:
            raise StoreComponentError(400, "No ip_address provided.")

        language = env.get("language", "en")
        description = item.description(language)

        total_float = total / 100.0

        arguments = {
            "uid": str(uid_parsed[1]),
            "ip": ip_address,
            "amount": '%.2f' % total_float,
            "item_id": item.item_id,
            "order_id": order_id,
            "account_id": account_id,
            "description": description
        }

        try:
            response = yield mailru_api.api_post("billing/client", private_key, **arguments)
        except APIError as e:
            raise StoreComponentError(e.code, e.body)

        url = response.get("url", None)

        if not url:
            raise StoreComponentError(500, "No url is returned")

        raise Return({
            "url": url
        })


StoreComponents.register_component("mailru", MailRuStoreComponent)
