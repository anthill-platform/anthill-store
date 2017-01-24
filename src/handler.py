

from tornado.gen import coroutine, Return
from tornado.web import HTTPError

from common.access import scoped, AccessToken
from common.handler import AuthenticatedHandler
from common import to_int

from model.store import StoreNotFound
from model.order import OrderError, NoOrderError

import ujson


class StoreHandler(AuthenticatedHandler):
    @scoped(["store"])
    @coroutine
    def get(self, store_name):

        stores = self.application.stores

        gamespace = self.token.get(AccessToken.GAMESPACE)

        try:
            store_data = yield stores.find_store_data(
                gamespace,
                store_name)

        except StoreNotFound:
            raise HTTPError(404, "Store not found")

        self.dumps({
            "store": store_data
        })


class NewOrderHandler(AuthenticatedHandler):
    @scoped(["store_order"])
    @coroutine
    def post(self):
        orders = self.application.orders

        store_name = self.get_argument("store")
        item_name = self.get_argument("item")
        currency_name = self.get_argument("currency")
        amount = to_int(self.get_argument("amount", "1"), 1)
        component_name = self.get_argument("component")

        gamespace_id = self.token.get(AccessToken.GAMESPACE)
        account_id = self.token.account

        env = self.get_argument("env", "{}")

        try:
            env = ujson.loads(env)
        except (KeyError, ValueError):
            raise HTTPError(400, "Corrupted env")

        try:
            order_id = yield orders.new_order(
                gamespace_id, account_id, store_name, component_name, item_name,
                currency_name, amount, env)
        except OrderError as e:
            raise HTTPError(e.code, e.message)

        self.dumps({
            "order_id": order_id
        })


class OrderHandler(AuthenticatedHandler):
    @scoped(["store_order"])
    @coroutine
    def post(self, order_id):
        orders = self.application.orders

        gamespace_id = self.token.get(AccessToken.GAMESPACE)
        account_id = self.token.account

        try:
            result = yield orders.update_order(gamespace_id, order_id, account_id)
        except NoOrderError:
            raise HTTPError(404, "No such order")
        except OrderError as e:
            raise HTTPError(e.code, e.message)

        self.dumps(result)
