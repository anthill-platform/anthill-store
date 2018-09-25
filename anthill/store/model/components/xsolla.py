
from tornado.httpclient import AsyncHTTPClient

from . import StoreComponent, StoreComponents, StoreComponentError

from ..order import OrdersModel, OrderError

from anthill.common import to_int
from anthill.common.social import APIError
from anthill.common.internal import Internal, InternalError

import logging

from urllib import parse
import ujson
import hashlib


class XsollaStoreComponent(StoreComponent):
    API_URL = "https://api.xsolla.com"

    def __init__(self):
        super(XsollaStoreComponent, self).__init__()
        self.sandbox = False
        self.project_id = 0
        self.internal = Internal()

        self.client = AsyncHTTPClient()

        self.NOTIFICATION_TYPES = {
            "payment": self.__notification_payment__,
            "user_validation": self.__notification_user_validation__
        }

    def dump(self):
        result = super(XsollaStoreComponent, self).dump()
        result.update({
            "sandbox": self.sandbox,
            "project_id": self.project_id,
        })
        return result

    def load(self, data):
        super(XsollaStoreComponent, self).load(data)
        self.sandbox = data.get("sandbox")
        self.project_id = to_int(data.get("project_id", 0))

    def __url__(self):
        return XsollaStoreComponent.API_URL

    def is_hook_applicable(self):
        return True

    async def update_order(self, app, gamespace_id, account_id, order, order_info):

        if order.status != OrdersModel.STATUS_APPROVED:
            raise StoreComponentError(409, "Order is not approved")

        result = (OrdersModel.STATUS_SUCCEEDED, {})
        return result

    async def order_callback(self, app, gamespace_id, store_id, arguments, headers, body_str):

        if body_str is None:
            raise StoreComponentError(400, {
                "error": {
                    "code": "CORRUPTED_JSON",
                    "message": "Json Object is corrupted"
                }
            })

        try:
            body = ujson.loads(body_str)
        except (KeyError, ValueError):
            raise StoreComponentError(400, {
                "error": {
                    "code": "CORRUPTED_JSON",
                    "message": "Json Object is corrupted"
                }
            })

        try:
            auth = headers["Authorization"]
        except KeyError:
            raise StoreComponentError(401, {
                "error": {
                    "code": "INVALID_SIGNATURE",
                    "message": "Authorization field is required"
                }
            })

        auth = auth.split(" ")

        if len(auth) != 2:
            raise StoreComponentError(401, {
                "error": {
                    "code": "INVALID_SIGNATURE",
                    "message": "Invalid signature"
                }
            })

        auth_method = auth[0]

        if auth_method != "Signature":
            raise StoreComponentError(401, {
                "error": {
                    "code": "INVALID_SIGNATURE",
                    "message": "Invalid signature"
                }
            })

        signature_value = auth[1]

        xsolla_api = app.xsolla_api

        private_key = await xsolla_api.get_private_key(gamespace_id)

        merchant_id = private_key.merchant_id
        project_key = private_key.project_key

        expected_value = hashlib.sha1(str(body_str) + str(project_key)).hexdigest().lower()

        if expected_value != signature_value:
            raise StoreComponentError(403, {
                "error": {
                    "code": "INVALID_SIGNATURE",
                    "message": "Invalid signature"
                }
            })

        try:
            notification_type = body["notification_type"]
        except KeyError:
            raise StoreComponentError(400, {
                "error": {
                    "code": "INVALID_PARAMETER",
                    "message": "notification_type is not defined"
                }
            })

        try:
            notification_type = self.NOTIFICATION_TYPES[notification_type]
        except KeyError:
            raise StoreComponentError(400, {
                "error": {
                    "code": "INVALID_PARAMETER",
                    "message": "No such notification_type"
                }
            })

        result = await notification_type(app, gamespace_id, store_id, arguments, headers, body)
        return result

    async def new_order(self, app, gamespace_id, account_id, order_id, currency,
                  price, amount, total, store, item, env, campaign_item):

        xsolla_api = app.xsolla_api

        private_key = await xsolla_api.get_private_key(gamespace_id)

        merchant_id = private_key.merchant_id
        api_key = private_key.api_key

        language = env.get("language", "en")
        description = item.description(language)

        total_float = total / 100.0

        arguments = {
            "user": {
                "id": {
                    "value": str(account_id),
                    "hidden": True
                }
            },
            "settings": {
                "project_id": self.project_id,
                "external_id": str(order_id),
                "currency": currency,
                "language": language,
                "ui": {
                    "size": "medium"
                }
            },
            "purchase": {
                "checkout": {
                    "currency": currency,
                    "amount": total_float
                },
                "description": {
                    "value": description
                }
            }
        }

        user_name = env.get("user_name")

        if user_name:
            arguments["user"]["name"] = {
                "value": user_name
            }

        if self.sandbox:
            arguments["settings"]["mode"] = "sandbox"

        try:
            response = await xsolla_api.api_post("token", merchant_id, api_key, **arguments)
        except APIError as e:
            raise StoreComponentError(e.code, e.body)

        token = response.get("token", None)

        if not token:
            raise StoreComponentError(500, "No token is returned")

        url = app.get_host() + "/front/xsolla?" + parse.urlencode({
            "access_token": token,
            "sandbox": self.sandbox
        })

        return {
            "token": token,
            "sandbox": True if self.sandbox == "true" else False,
            "url": url
        }

    async def __notification_payment__(self, app, gamespace_id, store_id, arguments, headers, body):

        logging.info("__notification_payment__: {0} {1} {2} {3} {4}".format(
            gamespace_id, store_id, ujson.dumps(arguments), ujson.dumps(headers), ujson.dumps(body)))

        try:
            transaction = body["transaction"]
        except KeyError:
            raise StoreComponentError(400, {
                "error": {
                    "code": "INVALID_PARAMETER",
                    "message": "transaction is not defined"
                }
            })

        dry_run = transaction.get("dry_run", 0) == 1

        try:
            transaction_id = transaction["id"]
        except KeyError:
            raise StoreComponentError(400, {
                "error": {
                    "code": "INVALID_PARAMETER",
                    "message": "transaction id is not defined"
                }
            })

        if dry_run and not self.sandbox:
            raise StoreComponentError(400, {
                "error": {
                    "code": "SECURITY_ERROR",
                    "message": "Sandbox modes mismatch"
                }
            })

        try:
            order_id = transaction["external_id"]
        except KeyError:
            raise StoreComponentError(400, {
                "error": {
                    "code": "INVALID_PARAMETER",
                    "message": "transaction[\"external_id\"] is not defined"
                }
            })

        orders = app.orders

        if dry_run:
            try:
                await orders.update_order_info(
                    gamespace_id, order_id, OrdersModel.STATUS_APPROVED,
                    {
                        "transaction_id": transaction_id
                    })
            except OrderError as e:
                raise StoreComponentError(e.code, {
                    "error": {
                        "code": "FAILED_TO_APPROVE",
                        "message": e.message
                    }
                })
            else:
                result = True
        else:
            try:
                result = await orders.update_order_status_reliable(
                    gamespace_id, order_id, OrdersModel.STATUS_CREATED, OrdersModel.STATUS_APPROVED,
                    {
                        "transaction_id": transaction_id
                    })
            except OrderError as e:
                raise StoreComponentError(e.code, {
                    "error": {
                        "code": "FAILED_TO_APPROVE",
                        "message": e.message
                    }
                })

        if not result:
            raise StoreComponentError(409, {
                "error": {
                    "code": "WRONG_STATE",
                    "message": "transaction is in wrong state, cannot approve"
                }
            })

        return {
            "status": "OK"
        }

    async def __notification_user_validation__(self, app, gamespace_id, store_id, arguments, headers, body):

        logging.info("__notification_user_validation__: {0} {1} {2} {3} {4}".format(
            gamespace_id, store_id, ujson.dumps(arguments), ujson.dumps(headers), ujson.dumps(body)))

        try:
            user = body["user"]
        except KeyError:
            raise StoreComponentError(400, {
                "error": {
                    "code": "INVALID_PARAMETER",
                    "message": "user is not defined"
                }
            })

        try:
            account = user["id"]
        except KeyError:
            raise StoreComponentError(400, {
                "error": {
                    "code": "INVALID_PARAMETER",
                    "message": "user[\"id\"] is not defined"
                }
            })

        try:
            result = await self.internal.request("login", "check_account_exists", account=str(account))
        except InternalError as e:
            raise StoreComponentError(500, {
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(e)
                }
            })

        if not isinstance(result, dict) or not result.get("exists", False):
            raise StoreComponentError(400, {
                "error": {
                    "code": "INVALID_USER",
                    "message": "No such user"
                }
            })

        return {
            "status": "OK"
        }


StoreComponents.register_component("xsolla", XsollaStoreComponent)
