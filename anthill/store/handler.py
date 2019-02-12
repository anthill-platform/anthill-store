
from tornado.web import HTTPError

from anthill.common.access import scoped, AccessToken, remote_ip
from anthill.common.handler import AuthenticatedHandler, AnthillRequestHandler
from anthill.common.validate import ValidationError, validate
from anthill.common.internal import InternalError
from anthill.common import to_int

from . model.store import StoreNotFound, StoreError
from . model.order import OrderError, NoOrderError, OrderQueryError

import ujson


class StoreHandler(AuthenticatedHandler):
    @scoped(["store"])
    async def get(self, store_name):
        stores = self.application.stores
        gamespace = self.token.get(AccessToken.GAMESPACE)

        extra_start_time = self.get_argument("extra_start_time", 0)
        extra_end_time = self.get_argument("extra_end_time", self.get_argument("extra_time", 0))

        try:
            store_data = await stores.build_store_data(
                gamespace, store_name, extra_start_time, extra_end_time)
        except StoreNotFound:
            raise HTTPError(404, "Store not found")
        except ValidationError as e:
            raise HTTPError(400, e.message)

        self.dumps({
            "store": store_data
        })


class NewOrderHandler(AuthenticatedHandler):
    @scoped(["store_order"])
    async def post(self):
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
        else:
            if "ip_address" not in env:
                env["ip_address"] = remote_ip(self.request)

        try:
            order_info = await orders.new_order(
                gamespace_id, account_id, store_name, component_name,
                item_name, currency_name, amount, env)
        except OrderError as e:
            raise HTTPError(e.code, e.message)
        except ValidationError as e:
            raise HTTPError(400, e.message)

        self.dumps(order_info)


class OrderHandler(AuthenticatedHandler):
    @scoped(["store_order"])
    async def post(self, order_id):
        orders = self.application.orders

        gamespace_id = self.token.get(AccessToken.GAMESPACE)
        account_id = self.token.account

        try:
            result = await orders.update_order(gamespace_id, order_id, account_id)
        except NoOrderError:
            raise HTTPError(404, "No such order")
        except OrderError as e:
            raise HTTPError(e.code, e.message)
        except ValidationError as e:
            raise HTTPError(400, e.message)

        self.dumps(result)


class OrdersHandler(AuthenticatedHandler):
    @scoped(["store_order"])
    async def post(self):
        orders = self.application.orders

        gamespace_id = self.token.get(AccessToken.GAMESPACE)
        account_id = self.token.account

        try:
            updated_orders = await orders.update_orders(gamespace_id, account_id)
        except OrderError as e:
            raise HTTPError(e.code, e.message)
        except ValidationError as e:
            raise HTTPError(400, e.message)

        self.dumps({
            "orders": updated_orders
        })


class WebHookHandler(AuthenticatedHandler):
    async def post(self, gamespace_id, store_name, component_name):
        orders = self.application.orders

        arguments = {
            key: value[0]
            for key, value in self.request.arguments.items()
        }

        headers = {
            key: value
            for key, value in self.request.headers.items()
        }

        body = self.request.body

        try:
            result = await orders.order_callback(gamespace_id, store_name, component_name, arguments, headers, body)
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

    async def get(self, gamespace_id, store_name, component_name):
        orders = self.application.orders

        arguments = {
            key: value[0]
            for key, value in self.request.arguments.items()
        }

        headers = {
            key: value
            for key, value in self.request.headers.items()
        }

        try:
            result = await orders.order_callback(gamespace_id, store_name, component_name, arguments, headers, "")
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

    @validate(gamespace="int", name="str_name")
    async def get_store(self, gamespace, name):

        try:
            store_data = await self.application.stores.build_store_data(gamespace, name)
        except StoreNotFound:
            raise InternalError(404, "Store not found")
        except ValidationError as e:
            raise InternalError(400, e.message)

        return {
            "store": store_data
        }

    @validate(gamespace="int", account="int", store="str_name", item="str_name",
              amount="int", component="str_name", env="json_dict")
    async def new_order(self, gamespace, account, store, item, currency, amount, component, env):

        try:
            result = await self.application.orders.new_order(
                gamespace, account, store, component, item, currency, amount, env)

        except OrderError as e:
            raise InternalError(e.code, e.message)
        except ValidationError as e:
            raise InternalError(400, e.message)

        return result

    @validate(gamespace="int", store="str_name", account="int", info="json_dict")
    async def list_orders(self, gamespace, store=None, account=None, info=None):

        orders = self.application.orders
        stores = self.application.stores

        if (account is None) and (info is None):
            raise InternalError(400, "Either account or info should be defined.")

        if store:
            try:
                store_id = await stores.find_store(gamespace, store)
            except StoreNotFound:
                raise InternalError(404, "No such store")
            except StoreError as e:
                raise InternalError(500, str(e))
        else:
            store_id = None

        q = orders.orders_query(gamespace, store_id)

        if account:
            q.account_id = account

        if info:
            q.info = info

        try:
            orders = await q.query()
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

        return {
            "orders": result
        }

    @validate(gamespace="int", account="int", order_id="int")
    async def update_order(self, gamespace, account, order_id):

        try:
            result = await self.application.orders.update_order(
                gamespace, order_id, account)

        except NoOrderError:
            raise HTTPError(404, "No such order")
        except OrderError as e:
            raise InternalError(e.code, e.message)
        except ValidationError as e:
            raise InternalError(400, e.message)

        return result

    @validate(gamespace="int", account="int")
    async def update_orders(self, gamespace, account):

        try:
            updated_orders = await self.application.orders.update_orders(
                gamespace, account)
        except OrderError as e:
            raise InternalError(e.code, e.message)
        except ValidationError as e:
            raise InternalError(400, e.message)

        return {
            "orders": updated_orders
        }


class XsollaFrontHandler(AnthillRequestHandler):
    def get(self):
        access_token = self.get_argument("access_token")
        sandbox = self.get_argument("sandbox", "false") == "true"

        self.render(
            "template/xsolla_form.html",
            access_token=access_token,
            sandbox="true" if sandbox else "false")
