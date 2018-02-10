
from tornado.gen import coroutine, Return
from tornado.web import HTTPError

from common.access import scoped, AccessToken
from common.handler import AuthenticatedHandler, AnthillRequestHandler
from common.validate import ValidationError, validate
from common.internal import InternalError
from common import to_int

from model.store import StoreNotFound, StoreError
from model.order import OrderError, NoOrderError, OrderQueryError

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
        except ValidationError as e:
            raise HTTPError(400, e.message)

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
            order_info = yield orders.new_order(
                gamespace_id, account_id, store_name, component_name, item_name,
                currency_name, amount, env)
        except OrderError as e:
            raise HTTPError(e.code, e.message)
        except ValidationError as e:
            raise HTTPError(400, e.message)

        self.dumps(order_info)


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
        except ValidationError as e:
            raise HTTPError(400, e.message)

        self.dumps(result)


class OrdersHandler(AuthenticatedHandler):
    @scoped(["store_order"])
    @coroutine
    def post(self):
        orders = self.application.orders

        gamespace_id = self.token.get(AccessToken.GAMESPACE)
        account_id = self.token.account

        try:
            updated_orders = yield orders.update_orders(gamespace_id, account_id)
        except OrderError as e:
            raise HTTPError(e.code, e.message)
        except ValidationError as e:
            raise HTTPError(400, e.message)

        self.dumps({
            "orders": updated_orders
        })


class WebHookHandler(AuthenticatedHandler):
    @coroutine
    def post(self, gamespace_id, store_name, component_name):
        orders = self.application.orders

        arguments = {
            key: value[0]
            for key, value in self.request.arguments.iteritems()
        }

        headers = {
            key: value
            for key, value in self.request.headers.iteritems()
        }

        body = self.request.body

        try:
            result = yield orders.order_callback(gamespace_id, store_name, component_name, arguments, headers, body)
        except NoOrderError:
            raise HTTPError(404, "No such order")
        except OrderError as e:
            self.set_status(e.code)
            if isinstance(e.message, dict):
                self.dumps(e.message)
                return

            self.write(e.message)
            return
        except ValidationError as e:
            raise HTTPError(400, e.message)

        if result:
            if isinstance(result, dict):
                self.dumps(result)
                return

            self.write(result)


class InternalHandler(object):
    def __init__(self, application):
        self.application = application

    @coroutine
    @validate(gamespace="int", name="str_name")
    def get_store(self, gamespace, name):

        try:
            store_data = yield self.application.stores.find_store_data(
                gamespace,
                name)

        except StoreNotFound:
            raise InternalError(404, "Store not found")
        except ValidationError as e:
            raise InternalError(400, e.message)

        raise Return({
            "store": store_data
        })

    @coroutine
    @validate(gamespace="int", account="int", store="str_name", item="str_name", amount="int", component="str_name")
    def new_order(self, gamespace, account, store, item, currency, amount, component):

        try:
            result = yield self.application.orders.new_order(
                gamespace, account, store, component, item, currency, amount, {})

        except OrderError as e:
            raise InternalError(e.code, e.message)
        except ValidationError as e:
            raise InternalError(400, e.message)

        raise Return(result)

    @coroutine
    @validate(gamespace="int", store="str_name", account="int", info="json_dict")
    def list_orders(self, gamespace, store=None, account=None, info=None):

        orders = self.application.orders
        stores = self.application.stores

        if (account is None) and (info is None):
            raise InternalError(400, "Either account or info should be defined.")

        if store:
            try:
                store_id = yield stores.find_store(gamespace, store)
            except StoreNotFound:
                raise InternalError(404, "No such store")
            except StoreError as e:
                raise InternalError(500, e.message)
        else:
            store_id = None

        q = orders.orders_query(gamespace, store_id)

        if account:
            q.account_id = account

        if info:
            q.info = info

        try:
            orders = yield q.query()
        except OrderQueryError as e:
            raise InternalError(e.code, e.message)
        except ValidationError as e:
            raise InternalError(400, e.message)

        result = {
            a.order.order_id: {
                "item": {
                    "name": a.item.name,
                    "public": a.item.public_data
                },
                "order": {
                    "status": a.order.status,
                    "time": str(a.order.time),
                    "currency": a.order.currency,
                    "amount": a.order.amount
                },
                "account": a.order.account_id,
                "component": a.component.name
            }
            for a in orders
        }

        raise Return({
            "orders": result
        })

    @coroutine
    @validate(gamespace="int", account="int", order_id="int")
    def update_order(self, gamespace, account, order_id):

        try:
            result = yield self.application.orders.update_order(
                gamespace, order_id, account)

        except NoOrderError:
            raise HTTPError(404, "No such order")
        except OrderError as e:
            raise InternalError(e.code, e.message)
        except ValidationError as e:
            raise InternalError(400, e.message)

        raise Return(result)

    @coroutine
    @validate(gamespace="int", account="int")
    def update_orders(self, gamespace, account):

        try:
            updated_orders = yield self.application.orders.update_orders(
                gamespace, account)
        except OrderError as e:
            raise InternalError(e.code, e.message)
        except ValidationError as e:
            raise InternalError(400, e.message)

        raise Return({
            "orders": updated_orders
        })


class XsollaFrontHandler(AnthillRequestHandler):
    def get(self):
        access_token = self.get_argument("access_token")
        sandbox = self.get_argument("sandbox", "false") == "true"

        self.render(
            "template/xsolla_form.html",
            access_token=access_token,
            sandbox="true" if sandbox else "false")
