
from tornado.gen import coroutine, Return

from store import StoreAdapter, StoreComponentAdapter, StoreError, StoreComponentNotFound
from item import ItemAdapter
from billing import IAPBillingMethod
from tier import TierError, TierNotFound, TierAdapter
from components import StoreComponents, StoreComponentError, NoSuchStoreComponentError

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
        self.order_id = data.get("order_id", None)


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

        self.tier_id = None
        self.item_id = None
        self.account_id = None
        self.component = None
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

        if self.tier_id:
            conditions.append("`orders`.`tier_id`=%s")
            data.append(str(self.tier_id))

        if self.item_id:
            conditions.append("`orders`.`item_id`=%s")
            data.append(str(self.item_id))

        if self.component:
            conditions.append("`orders`.`component_id`=%s")
            data.append(self.component)

        if self.account_id:
            conditions.append("`orders`.`account_id`=%s")
            data.append(str(self.account_id))

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
    STATUS_APPROVED = "APPROVED"
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
    def get_order_info(self, gamespace_id, order_id, account_id, db=None):
        try:
            data = yield (db or self.db).get(
                """
                    SELECT `store_components`.*, `items`.*, `stores`.*
                    FROM `orders`, `store_components`, `items`, `stores`
                    WHERE `orders`.`order_id`=%s AND `orders`.`gamespace_id`=%s
                        AND `orders`.`component_id`=`store_components`.`component_id`
                        AND `orders`.`gamespace_id`=`store_components`.`gamespace_id`
                        AND `items`.`item_id`=`orders`.`item_id`
                        AND `items`.`gamespace_id`=`orders`.`gamespace_id`
                        AND `stores`.`store_id`=`orders`.`store_id`
                        AND `orders`.`account_id` = %s;
                """, order_id, gamespace_id, account_id
            )
        except DatabaseError as e:
            raise OrderError(500, "Failed to gather order info: " + e.args[1])

        if not data:
            raise NoOrderError()

        raise Return(StoreComponentItemAdapter(data))

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

    @coroutine
    @validate(gamespace_id="int", order_id="int", old_status="str_name", new_status="str_name")
    def update_order_status_reliable(self, gamespace_id, order_id, old_status, new_status):
        try:
            with (yield self.db.acquire(auto_commit=False)) as db:

                try:
                    order = yield db.get(
                        """
                            SELECT * FROM `orders`
                            WHERE `order_status`=%s AND `order_id`=%s AND `gamespace_id`=%s
                            FOR UPDATE;
                        """, old_status, order_id, gamespace_id)

                    if not order:
                        raise Return(False)

                    yield db.execute(
                        """
                            UPDATE `orders`
                            SET `order_status`=%s
                            WHERE `order_id`=%s AND `gamespace_id`=%s;
                        """, new_status, order_id, gamespace_id)

                    raise Return(True)

                finally:
                    yield db.commit()

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
            try:
                data = yield self.__gather_order_info__(gamespace_id, store, component, item, "iap", db=db)
            except NoOrderError:
                raise OrderError(404, "Not found (either store, or currency, or component, or item, "
                                      "or item does not support such currency)")

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
                    self.app, gamespace_id, account_id, order_id, currency,
                    price, amount, total, data.store, data.item, env)

            except StoreComponentError as e:
                logging.exception("Failed to process new order")
                yield self.update_order_status(gamespace_id, order_id, OrdersModel.STATUS_ERROR, db=db)
                raise OrderError(e.code, e.message)

            result = {
                "order_id": order_id
            }

            if info:
                result.update(info)
                yield self.update_order_info(gamespace_id, order_id, OrdersModel.STATUS_CREATED, info, db=db)

            raise Return(result)

    @coroutine
    def __process_order_error__(self, gamespace_id, order, order_info, update_status, account_id, db):
        logging.warning("Processing failed order", extra={
            "gamespace": gamespace_id,
            "order": order.order_id,
            "account": account_id
        })

        raise OrderError(409, "Order has failed")

    @coroutine
    def __process_order_processing__(self, gamespace_id, order, order_info, update_status, account_id, db):
        component_name = order_info.component.name
        component_instance = StoreComponents.component(component_name, order_info.component.data)

        try:
            update = yield component_instance.update_order(
                self.app, gamespace_id, account_id, order, order_info)
        except StoreComponentError as e:
            logging.exception("Failed to update order", extra={
                "gamespace": gamespace_id,
                "order": order.order_id,
                "account": account_id
            })

            if e.update_status:
                new_status, new_info = e.update_status
                yield update_status(new_status, new_info)

            raise OrderError(e.code, e.message)
        else:
            logging.info("Order succeeded!", extra={
                "gamespace": gamespace_id,
                "order": order.order_id,
                "account": account_id,
                "status": OrdersModel.STATUS_SUCCEEDED,
                "amount": order.amount
            })

            new_status, new_info = update

            yield update_status(new_status, new_info)

            raise Return({
                "item": order_info.item.name,
                "amount": order.amount,
                "currency": order.currency,
                "store": order_info.store.name,
                "total": order.total,
                "order_id": to_int(order.order_id),
                "public": order_info.item.public_data,
                "private": order_info.item.private_data
            })

    @coroutine
    def __process_order_succeeded__(self, gamespace_id, order, order_info, update_status, account_id, db):
        logging.warning("Processing already succeeded order", extra={
            "gamespace": gamespace_id,
            "order": order.order_id,
            "account": account_id
        })
        raise OrderError(409, "Order has been succeeded already")

    @coroutine
    @validate(gamespace_id="int", store_name="str_name", component_name="str_name",
              arguments="json_dict", headers="json_dict", body="str")
    def order_callback(self, gamespace_id, store_name, component_name, arguments, headers, body):
        stores = self.app.stores

        try:
            component = yield stores.find_store_name_component(gamespace_id, store_name, component_name)
        except StoreError as e:
            raise OrderError(500, e.message)
        except StoreComponentNotFound:
            raise OrderError(404, "No such store component")

        try:
            component_instance = StoreComponents.component(component_name, component.data)
        except NoSuchStoreComponentError:
            raise OrderError(404, "No such store component implementation")

        try:
            result = yield component_instance.order_callback(self.app, gamespace_id, component.store_id,
                                                             arguments, headers, body)
        except StoreComponentError as e:
            logging.exception("Failed to process callback!")
            raise OrderError(e.code, e.message)

        raise Return(result)

    @coroutine
    @validate(gamespace_id="int", order_id="int", account_id="int")
    def update_order(self, gamespace_id, order_id, account_id, order_info=None):

        with (yield self.db.acquire(auto_commit=False)) as db:
            if not order_info:
                order_info = yield self.get_order_info(gamespace_id, order_id, account_id, db=db)

            try:
                try:
                    order_data = yield db.get(
                        """
                            SELECT *
                            FROM `orders`
                            WHERE `orders`.`order_id`=%s AND `orders`.`gamespace_id`=%s
                                AND `orders`.`account_id`=%s
                            FOR UPDATE;
                        """, order_id, gamespace_id, account_id
                    )
                except DatabaseError as e:
                    raise OrderError(500, "Failed to gather order info: " + e.args[1])

                if not order_data:
                    raise NoOrderError()

                order = OrderAdapter(order_data)

                @coroutine
                def update_status(new_status, new_info):

                    info = order.info or {}
                    info.update(new_info)

                    yield db.execute(
                        """
                            UPDATE `orders`
                            SET `order_status`=%s, `order_info`=%s
                            WHERE `orders`.`order_id`=%s AND `orders`.`gamespace_id`=%s
                                AND `orders`.`account_id`=%s;
                        """, new_status, ujson.dumps(info), order_id, gamespace_id, account_id)

                    logging.info("Updated order '{0}' status to: {1}".format(order_id, new_status))

                order_status = order.status

                if order_status not in OrdersModel.ORDER_PROCESSORS:
                    raise OrderError(406, "Order is in bad condition")

                update = yield OrdersModel.ORDER_PROCESSORS[order_status](
                    self, gamespace_id, order, order_info, update_status, account_id, db=db)

                raise Return(update)

            finally:
                yield db.commit()

    @coroutine
    @validate(gamespace_id="int", account_id="int")
    def update_orders(self, gamespace_id, account_id):

        with (yield self.db.acquire()) as db:

            order_statuses = [OrdersModel.STATUS_CREATED, OrdersModel.STATUS_APPROVED]

            try:
                orders_data = yield db.query(
                    """
                        SELECT `store_components`.*, `items`.*, `stores`.*, `orders`.`order_id`
                        FROM `orders`, `store_components`, `items`, `stores`
                        WHERE `orders`.`order_status` IN %s AND `orders`.`gamespace_id`=%s
                            AND `orders`.`component_id`=`store_components`.`component_id`
                            AND `orders`.`gamespace_id`=`store_components`.`gamespace_id`
                            AND `items`.`item_id`=`orders`.`item_id`
                            AND `items`.`gamespace_id`=`orders`.`gamespace_id`
                            AND `stores`.`store_id`=`orders`.`store_id`
                            AND `orders`.`account_id` = %s

                            ORDER BY `orders`.`order_id` DESC
                            LIMIT 10;
                    """, order_statuses, gamespace_id, account_id
                )
            except DatabaseError as e:
                raise OrderError(500, "Failed to gather order info: " + e.args[1])

            orders_info = map(StoreComponentItemAdapter, orders_data)

            update = []

            for info in orders_info:
                order_id = info.order_id

                if not order_id:
                    continue

                try:
                    update_result = yield self.update_order(
                        gamespace_id, order_id, account_id, order_info=info)
                except OrderError:
                    pass
                except NoOrderError:
                    pass
                else:
                    update.append(update_result)

            raise Return(update)

    ORDER_PROCESSORS = {
        STATUS_ERROR: __process_order_error__,
        STATUS_CREATED: __process_order_processing__,
        STATUS_APPROVED: __process_order_processing__,
        STATUS_SUCCEEDED: __process_order_succeeded__
    }