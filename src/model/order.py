
from tornado.gen import coroutine, Return

from store import StoreAdapter, StoreComponentAdapter
from item import ItemAdapter
from billing import IAPBillingMethod
from tier import TierError, TierNotFound, TierAdapter
from components import StoreComponents, StoreComponentError

from common.model import Model
from common.database import DatabaseError
from common.validate import validate
from common import to_int


import logging
import ujson


class OrderAdapter(object):
    def __init__(self, data):
        self.order_id = str(data.get("order_id"))
        self.store_id = str(data.get("store_id"))
        self.tier_id = str(data.get("tier_id"))
        self.item_id = str(data.get("item_id"))
        self.component_id = str(data.get("component_id"))
        self.account_id = str(data.get("account_id"))
        self.amount = data.get("order_amount")
        self.status = data.get("order_status")
        self.time = data.get("order_time")
        self.currency = data.get("order_currency")
        self.total = data.get("order_total")
        self.info = data.get("order_info")


class StoreComponentItemAdapter(object):
    def __init__(self, data):
        self.store = StoreAdapter(data)
        self.component = StoreComponentAdapter(data)
        self.item = ItemAdapter(data)


class OrderStoreComponentItemAdapter(object):
    def __init__(self, data):
        self.order = OrderAdapter(data)
        self.component = StoreComponentAdapter(data)
        self.item = ItemAdapter(data)
        self.store = StoreAdapter(data)


class OrderComponentTierItemAdapter(object):
    def __init__(self, data):
        self.order = OrderAdapter(data)
        self.component = StoreComponentAdapter(data)
        self.item = ItemAdapter(data)
        self.tier = TierAdapter(data)


class OrderError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message

    def __str__(self):
        return self.message


class NoOrderError(Exception):
    pass


class OrderQueryError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


class OrderQuery(object):
    def __init__(self, gamespace_id, store_id, db):
        self.gamespace_id = gamespace_id
        self.store_id = store_id
        self.db = db

        self.tier = None
        self.item = None
        self.component = None
        self.account = None
        self.status = None
        self.currency = None

        self.offset = 0
        self.limit = 0

    def __values__(self):
        conditions = [
            "`orders`.`gamespace_id`=%s",
            "`orders`.`store_id`=%s",
            "`orders`.`component_id`=`store_components`.`component_id`",
            "`orders`.`gamespace_id`=`store_components`.`gamespace_id`",
            "`items`.`item_id`=`orders`.`item_id`",
            "`items`.`gamespace_id`=`orders`.`gamespace_id`",
            "`orders`.`tier_id`=`tiers`.`tier_id`"
        ]

        data = [
            str(self.gamespace_id),
            str(self.store_id)
        ]

        if self.tier:
            conditions.append("`orders`.`tier_id`=%s")
            data.append(str(self.tier))

        if self.item:
            conditions.append("`orders`.`item_id`=%s")
            data.append(str(self.item))

        if self.component:
            conditions.append("`orders`.`component_id`=%s")
            data.append(self.component)

        if self.account:
            conditions.append("`orders`.`account_id`=%s")
            data.append(str(self.account))

        if self.currency:
            conditions.append("`orders`.`order_currency`=%s")
            data.append(str(self.currency))

        if self.status:
            conditions.append("`orders`.`order_status`=%s")
            data.append(str(self.status))

        return conditions, data

    @coroutine
    def query(self, one=False, count=False):
        conditions, data = self.__values__()

        query = """
            SELECT {0} * FROM `orders`, `items`, `store_components`, tiers
            WHERE {1}
        """.format(
            "SQL_CALC_FOUND_ROWS" if count else "",
            " AND ".join(conditions))

        query += """
            ORDER BY `order_time` DESC
        """

        if self.limit:
            query += """
                LIMIT %s,%s
            """
            data.append(int(self.offset))
            data.append(int(self.limit))

        query += ";"

        if one:
            try:
                result = yield self.db.get(query, *data)
            except DatabaseError as e:
                raise OrderQueryError("Failed to get message: " + e.args[1])

            if not result:
                raise Return(None)

            raise Return(OrderComponentTierItemAdapter(result))
        else:
            try:
                result = yield self.db.query(query, *data)
            except DatabaseError as e:
                raise OrderQueryError("Failed to query messages: " + e.args[1])

            count_result = 0

            if count:
                count_result = yield self.db.get(
                    """
                        SELECT FOUND_ROWS() AS count;
                    """)
                count_result = count_result["count"]

            items = map(OrderComponentTierItemAdapter, result)

            if count:
                raise Return((items, count_result))

            raise Return(items)


class OrdersModel(Model):

    STATUS_NEW = "NEW"
    STATUS_ERROR = "ERROR"
    STATUS_CREATED = "CREATED"
    STATUS_SUCCEEDED = "SUCCEEDED"

    def __init__(self, app, db, tiers):
        self.app = app
        self.db = db
        self.tiers = tiers

    def get_setup_tables(self):
        return ["orders"]

    def get_setup_db(self):
        return self.db

    @coroutine
    def __gather_order_info__(self, gamespace_id, store, component, item, item_method, db=None):
        try:
            data = yield (db or self.db).get(
                """
                    SELECT *
                    FROM `stores`, `items`, `store_components`
                    WHERE `stores`.`store_name`=%s AND `stores`.`gamespace_id`=%s
                        AND `store_components`.`component`=%s
                        AND `items`.`item_name`=%s AND `items`.`gamespace_id`=`stores`.`gamespace_id`
                        AND `store_components`.`store_id`=`stores`.`store_id`
                        AND `store_components`.`gamespace_id`=`stores`.`gamespace_id`
                        AND `items`.`store_id`=`stores`.`store_id` AND `items`.`item_method`=%s;
                """, store, gamespace_id, component, item, item_method
            )
        except DatabaseError as e:
            raise OrderError(500, "Failed to gather order info: " + e.args[1])

        if not data:
            raise NoOrderError()

        raise Return(StoreComponentItemAdapter(data))

    @coroutine
    @validate(gamespace_id="int", order_id="int")
    def get_order(self, gamespace_id, order_id, db=None):
        try:
            data = yield (db or self.db).get(
                """
                    SELECT *
                    FROM `orders`
                    WHERE `order_id`=%s AND `gamespace_id`=%s;
                """, order_id, gamespace_id
            )
        except DatabaseError as e:
            raise OrderError(500, "Failed to gather order info: " + e.args[1])

        if not data:
            raise NoOrderError()

        raise Return(OrderAdapter(data))

    @coroutine
    @validate(gamespace_id="int", order_id="int")
    def get_order_info(self, gamespace_id, order_id, db=None):
        try:
            data = yield (db or self.db).get(
                """
                    SELECT *
                    FROM `orders`, `store_components`, `items`, `stores`
                    WHERE `orders`.`order_id`=%s AND `orders`.`gamespace_id`=%s
                        AND `orders`.`component_id`=`store_components`.`component_id`
                        AND `orders`.`gamespace_id`=`store_components`.`gamespace_id`
                        AND `items`.`item_id`=`orders`.`item_id`
                        AND `items`.`gamespace_id`=`orders`.`gamespace_id`
                        AND `stores`.`store_id`=`orders`.`store_id`;
                """, order_id, gamespace_id
            )
        except DatabaseError as e:
            raise OrderError(500, "Failed to gather order info: " + e.args[1])

        if not data:
            raise NoOrderError()

        raise Return(OrderStoreComponentItemAdapter(data))

    @coroutine
    @validate(gamespace_id="int", order_id="int", status="str_name", info="json")
    def update_order_info(self, gamespace_id, order_id, status, info, db=None):
        try:
            yield (db or self.db).execute(
                """
                    UPDATE `orders`
                    SET `order_info`=%s, `order_status`=%s
                    WHERE `order_id`=%s AND `gamespace_id`=%s;
                """, ujson.dumps(info), status, order_id, gamespace_id)
        except DatabaseError as e:
            raise OrderError(500, e.args[1])

    @coroutine
    @validate(gamespace_id="int", order_id="int", status="str_name")
    def update_order_status(self, gamespace_id, order_id, status, db=None):
        try:
            yield (db or self.db).execute(
                """
                    UPDATE `orders`
                    SET `order_status`=%s
                    WHERE `order_id`=%s AND `gamespace_id`=%s;
                """, status, order_id, gamespace_id)
        except DatabaseError as e:
            raise OrderError(500, e.args[1])

    def orders_query(self, gamespace, store_id):
        return OrderQuery(gamespace, store_id, self.db)

    @coroutine
    @validate(gamespace_id="int", account_id="int", store="str_name", component="str_name", item="str_name",
              currency="str_name", amount="int", env="json")
    def new_order(self, gamespace_id, account_id, store, component, item, currency, amount, env):

        if (not isinstance(amount, int)) or amount <= 0:
            raise OrderError(400, "Invalid amount")

        if not StoreComponents.has_component(component):
            raise OrderError(404, "No such component")

        with (yield self.db.acquire()) as db:
            data = yield self.__gather_order_info__(gamespace_id, store, component, item, "iap", db=db)

            store_id = data.store.store_id
            item_id = data.item.item_id
            component_id = data.component.component_id

            billing = IAPBillingMethod()
            billing.load(data.item.method_data)

            try:
                tier = yield self.tiers.find_tier(gamespace_id, store_id, billing.tier)
            except TierError as e:
                raise OrderError(500, e.message)
            except TierNotFound:
                raise OrderError(404, "Tier was not found")

            if currency not in tier.prices:
                raise OrderError(404, "No such currency for a tier")

            tier_id = tier.tier_id
            price = tier.prices[currency]
            total = price * amount

            try:
                order_id = yield db.insert(
                    """
                        INSERT INTO `orders`
                            (`gamespace_id`, `store_id`, `tier_id`, `item_id`, `account_id`,
                             `component_id`, `order_amount`, `order_status`, `order_currency`, `order_total`)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, gamespace_id, store_id, tier_id, item_id, account_id, component_id,
                    amount, OrdersModel.STATUS_NEW, currency, total
                )
            except DatabaseError as e:
                raise OrderError(500, "Failed to create new order: " + e.args[1])

            component_instance = StoreComponents.component(component, data.component.data)

            try:
                info = yield component_instance.new_order(
                    self.app, gamespace_id, order_id, currency, price, amount, total, data.store, data.item, env)
            except StoreComponentError as e:
                logging.exception("Failed to process new order")
                yield self.update_order_status(gamespace_id, order_id, OrdersModel.STATUS_ERROR, db=db)
                raise OrderError(e.code, e.message)

            if info:
                yield self.update_order_info(gamespace_id, order_id, OrdersModel.STATUS_CREATED, info, db=db)

            raise Return(order_id)

    @coroutine
    def __process_order_error__(self, gamespace_id, data, account_id, db):
        logging.warning("Processing failed order", extra={
            "gamespace": gamespace_id,
            "order": data.order.order_id,
            "account": account_id
        })
        raise OrderError(409, "Order has failed")

    @coroutine
    def __process_order_processing__(self, gamespace_id, data, account_id, db):
        component_name = data.component.name
        component_instance = StoreComponents.component(component_name, data.component.data)

        try:
            yield component_instance.update_order(
                self.app, gamespace_id, account_id, data.order)
        except StoreComponentError as e:
            logging.exception("Failed to update order", extra={
                "gamespace": gamespace_id,
                "order": data.order.order_id,
                "account": account_id
            })
            raise OrderError(e.code, e.message)
        else:
            logging.info("Order succeeded!", extra={
                "gamespace": gamespace_id,
                "order": data.order.order_id,
                "account": account_id,
                "status": OrdersModel.STATUS_SUCCEEDED,
                "amount": data.order.amount
            })

            yield self.update_order_status(gamespace_id, data.order.order_id, OrdersModel.STATUS_SUCCEEDED, db=db)

            raise Return({
                "item": data.item.name,
                "amount": data.order.amount,
                "currency": data.order.currency,
                "store": data.store.name,
                "total": data.order.total,
                "order_id": to_int(data.order.order_id)
            })

    @coroutine
    def __process_order_succeeded__(self, gamespace_id, data, account_id, db):
        logging.warning("Processing already succeeded order", extra={
            "gamespace": gamespace_id,
            "order": data.order.order_id,
            "account": account_id
        })
        raise OrderError(423, "Order has been succeeded already.")

    @coroutine
    @validate(gamespace_id="int", order_id="int", account_id="int")
    def update_order(self, gamespace_id, order_id, account_id):

        with (yield self.db.acquire()) as db:
            order = yield self.get_order_info(gamespace_id, order_id, db=db)

            if order.order.account_id != account_id:
                raise NoOrderError()

            processors = {
                OrdersModel.STATUS_ERROR: self.__process_order_error__,
                OrdersModel.STATUS_CREATED: self.__process_order_processing__,
                OrdersModel.STATUS_SUCCEEDED: self.__process_order_succeeded__
            }

            order_status = order.order.status

            if order_status not in processors:
                raise OrderError(406, "Order is in bad condition")

            update = yield processors[order_status](gamespace_id, order, account_id, db=db)
            raise Return(update)
