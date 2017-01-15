
from tornado.gen import coroutine, Return
from tornado.httpclient import AsyncHTTPClient, HTTPRequest, HTTPError

from . import StoreComponent, StoreComponents, StoreComponentError

from common.social import steam

import urllib
import ujson


class SteamStoreComponent(StoreComponent):

    API_URL = "https://api.steampowered.com/ISteamMicroTxn"
    SANDBOX_API_URL = "https://api.steampowered.com/ISteamMicroTxnSandbox"

    def __init__(self):
        super(SteamStoreComponent, self).__init__()
        self.sandbox = False

        self.client = AsyncHTTPClient()

    def dump(self):
        result = super(SteamStoreComponent, self).dump()
        result.update({
            "sandbox": self.sandbox
        })
        return result

    def load(self, data):
        super(SteamStoreComponent, self).load(data)
        self.sandbox = data.get("sandbox")

    def __url__(self):
        return SteamStoreComponent.SANDBOX_API_URL if self.sandbox else SteamStoreComponent.API_URL

    @coroutine
    def update_order(self, app, gamespace_id, account_id, order):

        order_id = order.order_id
        steam_api = app.steam_api

        private_key = yield steam_api.get_private_key(gamespace_id)

        arguments = {
            "orderid": order_id,
            "appid": private_key.app_id,
            "key": private_key.key
        }

        request = HTTPRequest(
            url=self.__url__() + "/FinalizeTxn/V0001",
            method="POST",
            body=urllib.urlencode(arguments))

        try:
            response = yield self.client.fetch(request)
        except HTTPError as e:
            raise StoreComponentError(e.code, e.message)

        try:
            response = ujson.loads(response.body)["response"]
        except (KeyError, ValueError):
            raise StoreComponentError(500, "Corrupted FinalizeTxn response")

        failure = response.get("result", "Failure") != "OK"

        if failure:
            error = response.get("error", {})
            code = error.get("errorcode", 500)
            reason = error.get("errordesc", "Unknown")
            raise StoreComponentError(code, reason)

        params = response.get("params", {})

        steam_order_id = params.get("orderid", 0)

        if str(steam_order_id) != str(order_id):
            raise StoreComponentError(500, "OrderID does not correspond the steam OrderId")

        transaction_id = params.get("transid", 0)

        if not transaction_id:
            raise StoreComponentError(500, "No TransactionID")

        raise Return({
            "transaction_id": transaction_id
        })

    # noinspection SpellCheckingInspection
    @coroutine
    def new_order(self, app, gamespace_id, order_id, currency, price, amount, total, store, item, env):

        steam_id = env.get("steam_id")

        if not steam_id:
            raise StoreComponentError(400, "No username environment variable")

        steam_api = app.steam_api

        private_key = yield steam_api.get_private_key(gamespace_id)

        language = env.get("language", "EN")
        description = item.description(language)

        arguments = {
            "orderid": order_id,
            "steamid": steam_id,
            "appid": private_key.app_id,
            "itemcount": 1,
            "language": language,
            "currency": currency,
            "usersession": "client",
            "key": private_key.key,

            "itemid[0]": item.item_id,
            "qty[0]": amount,
            "amount[0]": int(float(total) * 100),
            "description[0]": description
        }

        category = item.data.get("category")

        if category:
            arguments["category[0]"] = arguments

        request = HTTPRequest(
            url=self.__url__() + "/InitTxn/V0002",
            method="POST",
            body=urllib.urlencode(arguments))

        try:
            response = yield self.client.fetch(request)
        except HTTPError as e:
            raise StoreComponentError(e.code, e.message)

        try:
            response = ujson.loads(response.body)["response"]
        except (KeyError, ValueError):
            raise StoreComponentError(500, "Corrupted InitTxn response")

        failure = response.get("result", "Failure") != "OK"

        if failure:
            error = response.get("error", {})
            code = error.get("errorcode", 500)
            reason = error.get("errordesc", "Unknown")
            raise StoreComponentError(code, reason)

        params = response.get("params", {})

        steam_order_id = params.get("orderid", 0)

        if str(steam_order_id) != str(order_id):
            raise StoreComponentError(500, "OrderID does not correspond the steam OrderId")

        transaction_id = params.get("transid", 0)

        if not transaction_id:
            raise StoreComponentError(500, "No TransactionID")

        raise Return({
            "transaction_id": transaction_id
        })


StoreComponents.register_component("steam", SteamStoreComponent)
