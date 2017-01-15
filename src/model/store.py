
from tornado.gen import coroutine, Return

from common.database import DatabaseError
from common.model import Model
import ujson


class StoreAdapter(object):
    def __init__(self, record):
        self.store_id = record["store_id"]
        self.name = record["store_name"]
        self.data = record.get("json")


class StoreComponentAdapter(object):
    def __init__(self, record):
        self.component_id = record["component_id"]
        self.name = record["component"]
        self.data = record["component_data"]


class StoreComponentNotFound(Exception):
    pass


class StoreModel(Model):
    def __init__(self, db, items, tiers, currencies):
        self.db = db
        self.items = items
        self.tiers = tiers
        self.currencies = currencies

    def get_setup_db(self):
        return self.db

    def get_setup_tables(self):
        return ["stores", "store_components"]

    @coroutine
    def delete_store(self, gamespace_id, store_id):
        try:
            with (yield self.db.acquire()) as db:
                yield db.execute("""
                    DELETE
                    FROM `items`
                    WHERE `store_id`=%s AND `gamespace_id`=%s;
                """, store_id, gamespace_id)

                yield db.execute("""
                    DELETE
                    FROM `stores`
                    WHERE `store_id`=%s AND `gamespace_id`=%s;
                """, store_id, gamespace_id)

                yield db.execute("""
                    DELETE
                    FROM `store_components`
                    WHERE `store_id`=%s AND `gamespace_id`=%s;
                """, store_id, gamespace_id)
        except DatabaseError as e:
            raise StoreError("Failed to delete store: " + e.args[1])

    @coroutine
    def delete_store_component(self, gamespace_id, store_id, component_id):
        try:
            yield self.db.execute("""
                DELETE
                FROM `store_components`
                WHERE `store_id`=%s AND `gamespace_id`=%s AND `component_id`=%s;
            """, store_id, gamespace_id, component_id)
        except DatabaseError as e:
            raise StoreError("Failed to delete store component: " + e.args[1])

    @coroutine
    def find_store(self, gamespace_id, store_name):
        try:
            result = yield self.db.get("""
                SELECT *
                FROM `stores`
                WHERE `store_name`=%s AND `gamespace_id`=%s;
            """, store_name, gamespace_id)
        except DatabaseError as e:
            raise StoreError("Failed to find store: " + e.args[1])

        if result is None:
            raise StoreNotFound()

        raise Return(StoreAdapter(result))

    @coroutine
    def find_store_component(self, gamespace_id, store_id, component_name):
        try:
            result = yield self.db.get("""
                SELECT *
                FROM `store_components`
                WHERE `store_id`=%s AND `gamespace_id`=%s AND `component`=%s;
            """, store_id, gamespace_id, component_name)
        except DatabaseError as e:
            raise StoreError("Failed to find store component: " + e.args[1])

        if result is None:
            raise StoreComponentNotFound()

        raise Return(StoreComponentAdapter(result))

    @coroutine
    def find_store_data(self, gamespace_id, store_name):
        try:
            result = yield self.db.get("""
                SELECT `json`
                FROM `stores`
                WHERE `store_name`=%s AND `gamespace_id`=%s;
            """, store_name, gamespace_id)
        except DatabaseError as e:
            raise StoreError("Failed to find store data: " + e.args[1])

        if result is None:
            raise StoreNotFound()

        result = result["json"]

        raise Return(result)

    @coroutine
    def get_store(self, gamespace_id, store_id):
        try:
            result = yield self.db.get("""
                SELECT *
                FROM `stores`
                WHERE `store_id`=%s AND `gamespace_id`=%s;
            """, store_id, gamespace_id)
        except DatabaseError as e:
            raise StoreError("Failed to get store: " + e.args[1])

        if result is None:
            raise StoreNotFound()

        raise Return(StoreAdapter(result))

    @coroutine
    def get_store_component(self, gamespace_id, store_id, component_id):
        try:
            result = yield self.db.get("""
                SELECT *
                FROM `store_components`
                WHERE `store_id`=%s AND `gamespace_id`=%s AND `component_id`=%s;
            """, store_id, gamespace_id, component_id)
        except DatabaseError as e:
            raise StoreError("Failed to get store component: " + e.args[1])

        if result is None:
            raise StoreComponentNotFound()

        raise Return(StoreComponentAdapter(result))

    @coroutine
    def get_store_data(self, gamespace_id, store_id):
        result = yield self.db.get("""
            SELECT `json`
            FROM `stores`
            WHERE `store_id`=%s AND `gamespace_id`=%s;
        """, store_id, gamespace_id)

        if result is None:
            raise StoreNotFound()

        result = result["json"]

        raise Return(result)

    @coroutine
    def list_store_components(self, gamespace_id, store_id):
        try:
            result = yield self.db.query("""
                SELECT *
                FROM `store_components`
                WHERE `store_id`=%s AND `gamespace_id`=%s;
            """, store_id, gamespace_id)
        except DatabaseError as e:
            raise StoreError("Failed to list store components: " + e.args[1])
        else:
            raise Return(map(StoreComponentAdapter, result))

    @coroutine
    def list_stores(self, gamespace_id):
        result = yield self.db.query("""
            SELECT `store_name`, `store_id`
            FROM `stores`
            WHERE `gamespace_id`=%s;
        """, gamespace_id)

        raise Return(map(StoreAdapter, result))

    @coroutine
    def new_store(self, gamespace_id, store_name):

        try:
            yield self.find_store(gamespace_id, store_name)
        except StoreNotFound:
            pass
        else:
            raise StoreError("Store '{0}' already exists.".format(store_name))

        try:
            store_id = yield self.db.insert("""
                INSERT INTO `stores`
                (`gamespace_id`, `store_name`, `json`)
                VALUES (%s, %s, %s);
            """, gamespace_id, store_name, "{}")
        except DatabaseError as e:
            raise StoreError("Failed to add new store: " + e.args[1])

        raise Return(store_id)

    @coroutine
    def new_store_component(self, gamespace_id, store_id, component_name, component_data):

        if not isinstance(component_data, dict):
            raise StoreError("Component data should be a dict")

        try:
            yield self.find_store_component(gamespace_id, store_id, component_name)
        except StoreComponentNotFound:
            pass
        else:
            raise StoreError("Store component '{0}' already exists.".format(component_name))

        try:
            component_id = yield self.db.insert("""
                INSERT INTO `store_components`
                (`gamespace_id`, `store_id`, `component`, `component_data`)
                VALUES (%s, %s, %s, %s);
            """, gamespace_id, store_id, component_name, ujson.dumps(component_data))
        except DatabaseError as e:
            raise StoreError("Failed to add new store component: " + e.args[1])

        raise Return(component_id)

    @coroutine
    def publish_store(self, gamespace_id, store_id):
        store_items = yield self.items.list_items(gamespace_id, store_id)
        store_tiers = yield self.tiers.list_tiers(gamespace_id, store_id)
        currencies = yield self.currencies.list_currencies(gamespace_id)

        currencies_data = {
            currency.name: {
                "title": currency.title,
                "format": currency.format,
                "symbol": currency.symbol,
                "label": currency.label
            } for currency in currencies
        }

        items = []

        for item in store_items:

            billing = item.method_data
            billing["type"] = item.method

            items.append({
                "id": item.name,
                "category": item.category.name,
                "payload": item.data,
                "billing": billing,
                "contents": item.contents
            })

        data = {
            "tiers":
            {
                tier.name: {
                    "product": tier.product,
                    "prices": {
                        currency: {
                            "title": currencies_data[currency]["title"],
                            "price": price,
                            "format": currencies_data[currency]["format"].format(price),
                            "symbol": currencies_data[currency]["symbol"],
                            "label": currencies_data[currency]["label"],
                        } for currency, price in tier.prices.iteritems()
                    }
                } for tier in store_tiers
            },
            "items": items
        }

        yield self.db.execute("""
            UPDATE `stores`
            SET `json`=%s
            WHERE `store_id`=%s AND `gamespace_id`=%s;
        """, ujson.dumps(data), store_id, gamespace_id)

    @coroutine
    def update_store(self, gamespace_id, store_id, store_name):
        try:
            yield self.db.execute("""
                UPDATE `stores`
                SET `store_name`=%s
                WHERE `store_id`=%s AND `gamespace_id`=%s;
            """, store_name, store_id, gamespace_id)
        except DatabaseError as e:
            raise StoreError("Failed to update content: " + e.args[1])

    @coroutine
    def update_store_component(self, gamespace_id, store_id, component_id, component_data):

        if not isinstance(component_data, dict):
            raise StoreError("Component data should be a dict")

        try:
            yield self.get_store_component(gamespace_id, store_id, component_id)
        except StoreComponentNotFound:
            raise StoreError("Store component not exists.")

        try:
            yield self.db.execute("""
                UPDATE `store_components`
                SET `component_data`=%s
                WHERE `store_id`=%s AND `gamespace_id`=%s AND `component_id`=%s;
            """, ujson.dumps(component_data), store_id, gamespace_id, component_id)
        except DatabaseError as e:
            raise StoreError("Failed to update store component: " + e.args[1])


class StoreError(Exception):
    pass


class StoreNotFound(Exception):
    pass
