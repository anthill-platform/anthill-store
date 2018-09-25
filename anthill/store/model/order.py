
from tornado.ioloop import PeriodicCallback

from . store import StoreAdapter, StoreComponentAdapter, StoreError, StoreComponentNotFound
from . item import StoreItemAdapter
from . tier import TierError, TierNotFound, TierAdapter
from . campaign import CampaignError, CampaignItemNotFound
from . components import StoreComponents, StoreComponentError, NoSuchStoreComponentError

from anthill.common.model import Model
from anthill.common.database import DatabaseError, format_conditions_json
from anthill.common.validate import validate
from anthill.common import to_int


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
        self.campaign_id = data.get("order_campaign_id")


class StoreComponentItemTierAdapter(object):
    def __init__(self, data):
        self.store = StoreAdapter(data)
        self.component = StoreComponentAdapter(data)
        self.item = StoreItemAdapter(data)
        self.tier = TierAdapter(data)
        self.order_id = data.get("order_id", None)


class OrderComponentTierItemAdapter(object):
    def __init__(self, data):
        self.order = OrderAdapter(data)
        self.component = StoreComponentAdapter(data)
        self.item = StoreItemAdapter(data)
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
    def __init__(self, code, message):
        self.code = code
        self.message = message

    def __str__(self):
        return str(self.code) + ": " + self.message


class OrderQuery(object):
    def __init__(self, gamespace_id, db, store_id=None):
        self.gamespace_id = gamespace_id
        self.store_id = store_id
        self.db = db

        self.tier_id = None
        self.item_id = None
        self.account_id = None
        self.component = None
        self.status = None
        self.currency = None
        self.info = None

        self.offset = 0
        self.limit = 0

    def __values__(self):
        conditions = [
            "`orders`.`gamespace_id`=%s",
            "`orders`.`component_id`=`store_components`.`component_id`",
            "`orders`.`gamespace_id`=`store_components`.`gamespace_id`",
            "`items`.`item_id`=`orders`.`item_id`",
            "`items`.`gamespace_id`=`orders`.`gamespace_id`",
            "`orders`.`tier_id`=`tiers`.`tier_id`"
        ]

        data = [
            str(self.gamespace_id)
        ]

        if self.store_id:
            conditions.append("`orders`.`store_id`=%s")
            data.append(str(self.store_id))

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

        if self.info:
            for condition, values in format_conditions_json('order_info', self.info):
                conditions.append(condition)
                data.extend(values)

        return conditions, data

    async def query(self, one=False, count=False):
        conditions, data = self.__values__()

        query = """
            SELECT {0} * FROM `orders`, `items`, `store_components`, `tiers`
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
                result = await self.db.get(query, *data)
            except DatabaseError as e:
                raise OrderQueryError(500, "Failed to get message: " + e.args[1])

            if not result:
                return None

            return OrderComponentTierItemAdapter(result)
        else:
            try:
                result = await self.db.query(query, *data)
            except DatabaseError as e:
                raise OrderQueryError(500, "Failed to query messages: " + e.args[1])

            count_result = 0

            if count:
                count_result = await self.db.get(
                    """
                        SELECT FOUND_ROWS() AS count;
                    """)
                count_result = count_result["count"]

            items = map(OrderComponentTierItemAdapter, result)

            if count:
                return (items, count_result)

            return items


class OrdersModel(Model):

    # The order has been just created, but yet not filed into the system
    STATUS_NEW = "NEW"
    # The order has been just created, and it's in the system now
    STATUS_CREATED = "CREATED"
    # The order has failed due to user issues (insufficient funds etc)
    STATUS_ERROR = "ERROR"
    # The order has failed due to network issues, thus should be retried
    STATUS_RETRY = "RETRY"
    # The order has been approved by a third party, the order update is required
    STATUS_APPROVED = "APPROVED"
    # The order has been rejected by a user
    STATUS_REJECTED = "REJECTED"
    # The order has been finalized
    STATUS_SUCCEEDED = "SUCCEEDED"

    def __init__(self, app, db, tiers, campaigns):
        self.app = app
        self.db = db
        self.tiers = tiers
        self.campaigns = campaigns

        if app.monitoring:
            logging.info("[room] Orders monitoring enabled.")
            self.monitoring_report_callback = PeriodicCallback(self.__update_monitoring_status__, 60000)
        else:
            self.monitoring_report_callback = None

    async def __update_monitoring_status__(self):

        successful_orders = await self.db.query("""
            SELECT `order_currency`, SUM(`order_total`) AS `order_total`
            FROM `orders`
            WHERE `order_status`='SUCCEEDED' AND `orders`.`order_time` > DATE_SUB(NOW(), INTERVAL 1 MINUTE)
            GROUP BY `order_currency`
        """)

        for successful_order in successful_orders:
            self.app.monitor_action("successful_orders", values={
                "total": successful_order["order_total"]
            }, currency=successful_order["order_currency"])

    async def started(self, application):
        await super(OrdersModel, self).started(application)
        if self.monitoring_report_callback:
            self.monitoring_report_callback.start()
            await self.__update_monitoring_status__()

    async def stopped(self):
        if self.monitoring_report_callback:
            self.monitoring_report_callback.stop()
        await super(OrdersModel, self).stopped()

    def get_setup_tables(self):
        return ["orders"]

    def get_setup_db(self):
        return self.db

    def has_delete_account_event(self):
        return True

    async def accounts_deleted(self, gamespace, accounts, gamespace_only):
        try:
            if gamespace_only:
                await self.db.execute(
                    """
                        DELETE FROM `orders`
                        WHERE `gamespace_id`=%s AND `account_id` IN %s;
                    """, gamespace, accounts)
            else:
                await self.db.execute(
                    """
                        DELETE FROM `orders`
                        WHERE `account_id` IN %s;
                    """, accounts)
        except DatabaseError as e:
            raise OrderError(500, "Failed to delete user orders: " + e.args[1])

    async def __gather_order_info__(self, gamespace_id, store, component, item, db=None):
        try:
            data = await (db or self.db).get(
                """
                    SELECT *
                    FROM `stores`, `items`, `store_components`, `tiers`
                    WHERE `stores`.`store_name`=%s AND `stores`.`gamespace_id`=%s
                        AND `store_components`.`component`=%s
                        AND `items`.`item_name`=%s AND `items`.`gamespace_id`=`stores`.`gamespace_id`
                        AND `store_components`.`store_id`=`stores`.`store_id`
                        AND `store_components`.`gamespace_id`=`stores`.`gamespace_id`
                        AND `items`.`store_id`=`stores`.`store_id`
                        AND `tiers`.`tier_id`=`items`.`item_tier`;
                """, store, gamespace_id, component, item
            )
        except DatabaseError as e:
            raise OrderError(500, "Failed to gather order info: " + e.args[1])

        if not data:
            raise NoOrderError()

        return StoreComponentItemTierAdapter(data)

    @validate(gamespace_id="int", order_id="int")
    async def get_order(self, gamespace_id, order_id, db=None):
        try:
            data = await (db or self.db).get(
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

        return OrderAdapter(data)

    @validate(gamespace_id="int", order_id="int")
    async def get_order_info(self, gamespace_id, order_id, account_id, db=None):
        try:
            data = await (db or self.db).get(
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

        return StoreComponentItemTierAdapter(data)

    @validate(gamespace_id="int", order_id="int", status="str_name", info="json")
    async def update_order_info(self, gamespace_id, order_id, status, info, db=None):
        try:
            await (db or self.db).execute(
                """
                    UPDATE `orders`
                    SET `order_info`=%s, `order_status`=%s
                    WHERE `order_id`=%s AND `gamespace_id`=%s;
                """, ujson.dumps(info), status, order_id, gamespace_id)
        except DatabaseError as e:
            raise OrderError(500, e.args[1])
        else:
            self.app.monitor_rate("orders", "updated", status=status)

    @validate(gamespace_id="int", order_id="int", status="str_name")
    async def update_order_status(self, gamespace_id, order_id, status, db=None):
        try:
            await (db or self.db).execute(
                """
                    UPDATE `orders`
                    SET `order_status`=%s
                    WHERE `order_id`=%s AND `gamespace_id`=%s;
                """, status, order_id, gamespace_id)
        except DatabaseError as e:
            raise OrderError(500, e.args[1])
        else:
            self.app.monitor_rate("orders", "updated", status=status)

    @validate(gamespace_id="int", order_id="int", old_status="str_name",
              new_status="str_name", ensure_order_total="int", ensure_item_id="int")
    async def update_order_status_reliable(self, gamespace_id, order_id, old_status,
                                     new_status, new_info=None,
                                     ensure_order_total=None, ensure_item_id=None):

        application = self.app

        try:
            async with self.db.acquire(auto_commit=False) as db:

                try:
                    order = await db.get(
                        """
                            SELECT * FROM `orders`
                            WHERE `order_status`=%s AND `order_id`=%s AND `gamespace_id`=%s
                            FOR UPDATE;
                        """, old_status, order_id, gamespace_id)

                    if not order:
                        return False

                    if ensure_order_total is not None:
                        order_total = int(order["order_total"])
                        if order_total != ensure_order_total:
                            raise OrderError(409, "Order has wrong total.")

                    if ensure_item_id is not None:
                        item_id = int(order["item_id"])
                        if item_id != ensure_item_id:
                            raise OrderError(409, "Order has wrong item_id.")

                    order_info = order["order_info"] or {}

                    if isinstance(new_info, dict):
                        order_info.update(new_info)

                    await db.execute(
                        """
                            UPDATE `orders`
                            SET `order_status`=%s, `order_info`=%s
                            WHERE `order_id`=%s AND `gamespace_id`=%s;
                        """, new_status, ujson.dumps(order_info), order_id, gamespace_id)

                    application.monitor_rate("orders", "updated", status=new_status)

                    return True

                finally:
                    await db.commit()

        except DatabaseError as e:
            raise OrderError(500, e.args[1])

    def orders_query(self, gamespace, store_id=None):
        return OrderQuery(gamespace, self.db, store_id)

    @validate(gamespace_id="int", account_id="int", store="str_name", component="str_name", item_name="str_name",
              currency="str_name", amount="int", env="json")
    async def new_order(self, gamespace_id, account_id, store_name, component_name, item_name, currency, amount, env):

        if (not isinstance(amount, int)) or amount <= 0:
            raise OrderError(400, "Invalid amount")

        if not StoreComponents.has_component(component_name):
            raise OrderError(404, "No such component")

        async with self.db.acquire() as db:
            try:
                data = await self.__gather_order_info__(gamespace_id, store_name, component_name, item_name, db=db)
            except NoOrderError:
                raise OrderError(404, "Not found (either store, or currency, or component, or item, "
                                      "or item does not support such currency)")

            item = data.item

            if not item.enabled:
                raise OrderError(410, "Order is disabled")

            store_id = data.store.store_id
            item_id = item.item_id
            component_id = data.component.component_id

            try:
                campaign_entry = await self.campaigns.find_current_campaign_item(gamespace_id, store_id, item_id)
            except CampaignError:
                tier = data.tier
                campaign_id = None
                campaign_item = None
            else:
                if campaign_entry is None:
                    tier = data.tier
                    campaign_id = None
                    campaign_item = None
                else:
                    # if there's an ongoing campaign that affects current item, then
                    # tier and certain item payload (public_data, private_data) should be updated
                    # from that campaign instead
                    tier = campaign_entry.tier
                    campaign_item = campaign_entry.campaign_item
                    campaign_id = campaign_item.campaign_id
                    item.apply_campaign(campaign_item)

            if currency not in tier.prices:
                raise OrderError(404, "No such currency for a tier")

            tier_id = tier.tier_id
            price = tier.prices[currency]
            total = price * amount

            try:
                order_id = await db.insert(
                    """
                        INSERT INTO `orders`
                            (`gamespace_id`, `store_id`, `tier_id`, `item_id`, `account_id`,
                             `component_id`, `order_amount`, `order_status`, `order_currency`, 
                             `order_total`, `order_campaign_id`)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, gamespace_id, store_id, tier_id, item_id, account_id, component_id,
                    amount, OrdersModel.STATUS_NEW, currency, total, campaign_id)
            except DatabaseError as e:
                raise OrderError(500, "Failed to create new order: " + e.args[1])

            component_instance = StoreComponents.component(component_name, data.component.data)

            try:
                info = await component_instance.new_order(
                    self.app, gamespace_id, account_id, order_id, currency, price,
                    amount, total, data.store, item, env, campaign_item)

            except StoreComponentError as e:
                logging.exception("Failed to process new order: " + e.message)
                await self.update_order_status(gamespace_id, order_id, OrdersModel.STATUS_ERROR, db=db)
                raise OrderError(e.code, e.message)

            result = {
                "order_id": order_id
            }

            if info:
                result.update(info)
                await self.update_order_status(gamespace_id, order_id, OrdersModel.STATUS_CREATED, db=db)

            return result

    async def __process_order_error__(self, gamespace_id, order, order_info, update_status, account_id, db):
        logging.warning("Processing failed order", extra={
            "gamespace": gamespace_id,
            "order": order.order_id,
            "account": account_id
        })

        raise OrderError(409, "Order has failed")

    async def __process_order_processing__(self, gamespace_id, order, order_info, update_status, account_id, db):
        component_name = order_info.component.name
        component_instance = StoreComponents.component(component_name, order_info.component.data)

        try:
            update = await component_instance.update_order(
                self.app, gamespace_id, account_id, order, order_info)
        except StoreComponentError as e:
            logging.exception("Failed to update order", extra={
                "gamespace": gamespace_id,
                "order": order.order_id,
                "account": account_id
            })

            if e.update_status:
                new_status, new_info = e.update_status
                await update_status(new_status, new_info)

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

            await update_status(new_status, new_info)

            item = order_info.item

            if order.campaign_id:
                try:
                    campaign = await self.campaigns.get_campaign_item(
                        gamespace_id, order.campaign_id, order.item_id, db)
                except CampaignItemNotFound:
                    pass
                except CampaignError:
                    pass
                else:
                    item.apply_campaign(campaign)

            return {
                "item": item.name,
                "amount": order.amount,
                "currency": order.currency,
                "store": order_info.store.name,
                "total": order.total,
                "order_id": to_int(order.order_id),
                "public": item.public_data,
                "private": item.private_data,
                "info": order.info
            }

    async def __process_order_succeeded__(self, gamespace_id, order, order_info, update_status, account_id, db):
        logging.warning("Processing already succeeded order", extra={
            "gamespace": gamespace_id,
            "order": order.order_id,
            "account": account_id
        })
        raise OrderError(409, "Order has been succeeded already")

    async def __process_order_rejected__(self, gamespace_id, order, order_info, update_status, account_id, db):
        logging.warning("Processing already rejected order", extra={
            "gamespace": gamespace_id,
            "order": order.order_id,
            "account": account_id
        })
        raise OrderError(409, "Order has been rejected already")

    @validate(gamespace_id="int", store_name="str_name", component_name="str_name",
              arguments="json_dict", headers="json_dict", body="str")
    async def order_callback(self, gamespace_id, store_name, component_name, arguments, headers, body):
        stores = self.app.stores

        try:
            component = await stores.find_store_name_component(gamespace_id, store_name, component_name)
        except StoreError as e:
            raise OrderError(500, str(e))
        except StoreComponentNotFound:
            raise OrderError(404, "No such store component")

        try:
            component_instance = StoreComponents.component(component_name, component.data)
        except NoSuchStoreComponentError:
            raise OrderError(404, "No such store component implementation")

        if not component_instance.is_hook_applicable():
            raise OrderError(400, "This store component does not allow hooks")

        try:
            result = await component_instance.order_callback(self.app, gamespace_id, component.store_id,
                                                             arguments, headers, body)
        except StoreComponentError as e:
            logging.exception("Failed to process callback!")
            raise OrderError(e.code, e.message)

        return result

    @validate(gamespace_id="int", order_id="int", account_id="int")
    async def update_order(self, gamespace_id, order_id, account_id, order_info=None):

        application = self.app

        async with self.db.acquire(auto_commit=False) as db:
            if not order_info:
                order_info = await self.get_order_info(gamespace_id, order_id, account_id, db=db)

            try:
                try:
                    order_data = await db.get(
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

                async def update_status(new_status, new_info):

                    info = order.info or {}
                    info.update(new_info)
                    order.info = info

                    await db.execute(
                        """
                            UPDATE `orders`
                            SET `order_status`=%s, `order_info`=%s
                            WHERE `orders`.`order_id`=%s AND `orders`.`gamespace_id`=%s
                                AND `orders`.`account_id`=%s;
                        """, new_status, ujson.dumps(info), order_id, gamespace_id, account_id)

                    application.monitor_rate("orders", "updated", status=new_status)

                    logging.info("Updated order '{0}' status to: {1}".format(order_id, new_status))

                order_status = order.status

                if order_status not in OrdersModel.ORDER_PROCESSORS:
                    raise OrderError(406, "Order is in bad condition")

                update = await OrdersModel.ORDER_PROCESSORS[order_status](
                    self, gamespace_id, order, order_info, update_status, account_id, db=db)

                return update

            finally:
                await db.commit()

    @validate(gamespace_id="int", account_id="int")
    async def update_orders(self, gamespace_id, account_id):

        async with self.db.acquire() as db:

            order_statuses = [OrdersModel.STATUS_CREATED, OrdersModel.STATUS_APPROVED, OrdersModel.STATUS_RETRY]

            try:
                orders_data = await db.query(
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

            orders_info = map(StoreComponentItemTierAdapter, orders_data)

            update = []

            for info in orders_info:
                order_id = info.order_id

                if not order_id:
                    continue

                try:
                    update_result = await self.update_order(
                        gamespace_id, order_id, account_id, order_info=info)
                except OrderError:
                    pass
                except NoOrderError:
                    pass
                else:
                    update.append(update_result)

            return update

    ORDER_PROCESSORS = {
        STATUS_ERROR: __process_order_error__,
        STATUS_CREATED: __process_order_processing__,
        STATUS_RETRY: __process_order_processing__,
        STATUS_APPROVED: __process_order_processing__,
        STATUS_SUCCEEDED: __process_order_succeeded__,
        STATUS_REJECTED: __process_order_rejected__
    }
