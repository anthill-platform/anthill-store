
from tornado.gen import coroutine, Return

from common.database import DatabaseError
from common.model import Model
import ujson


class CurrencyError(Exception):
    pass


class CurrencyModel(Model):
    def __init__(self, db):
        self.db = db

    def get_setup_db(self):
        return self.db

    def get_setup_tables(self):
        return ["currencies"]

    @coroutine
    def delete_currency(self, gamespace_id, currency_id):
        try:
            yield self.db.execute("""
                DELETE
                FROM `currencies`
                WHERE `currency_id`=%s AND `gamespace_id`=%s;
            """, currency_id, gamespace_id)
        except DatabaseError as e:
            raise PackError("Failed to delete currency: " + e.args[1])

    @coroutine
    def find_currency(self, gamespace_id, currency_name):
        try:
            result = yield self.db.get("""
                SELECT *
                FROM `currencies`
                WHERE `currency_name`=%s AND `gamespace_id`=%s;
            """, currency_name, gamespace_id)
        except DatabaseError as e:
            raise PackError("Failed to find currency: " + e.args[1])

        if result is None:
            raise CurrencyNotFound()

        raise Return(result)

    @coroutine
    def get_currency(self, gamespace_id, currency_id):
        try:
            result = yield self.db.get("""
                SELECT *
                FROM `currencies`
                WHERE `currency_id`=%s AND `gamespace_id`=%s;
            """, currency_id, gamespace_id)
        except DatabaseError as e:
            raise PackError("Failed to get currency: " + e.args[1])

        if result is None:
            raise CurrencyNotFound()

        raise Return(result)

    @coroutine
    def list_currencies(self, gamespace_id):
        try:
            result = yield self.db.query("""
                SELECT *
                FROM `currencies`
                WHERE `gamespace_id`=%s;
            """, gamespace_id)
        except DatabaseError as e:
            raise PackError("Failed to list currencies: " + e.args[1])

        raise Return(result)

    @coroutine
    def new_currency(self, gamespace_id, currency_name, currency_title, currency_format,
                     currency_symbol, currency_label):

        try:
            yield self.find_currency(gamespace_id, currency_name)
        except CurrencyNotFound:
            pass
        else:
            raise PackError("Currency '{0}' already exists is such store.".format(currency_name))

        try:
            result = yield self.db.insert("""
                INSERT INTO `currencies`
                (`gamespace_id`, `currency_name`, `currency_title`, `currency_format`, `currency_symbol`,
                `currency_label`)
                VALUES (%s, %s, %s, %s, %s, %s);
            """, gamespace_id, currency_name, currency_title, currency_format, currency_symbol, currency_label)
        except DatabaseError as e:
            raise CurrencyError("Failed to add new currency: " + e.args[1])

        raise Return(result)

    @coroutine
    def update_currency(self, gamespace_id, currency_id, currency_name, currency_title, currency_format,
                        currency_symbol, currency_label):
        try:
            yield self.db.execute("""
                UPDATE `currencies`
                SET `currency_name`=%s, `currency_title`=%s, `currency_format`=%s, `currency_symbol`=%s,
                    `currency_label`=%s
                WHERE `currency_id`=%s AND `gamespace_id`=%s;
            """, currency_name, currency_title, currency_format, currency_symbol, currency_label,
                                  currency_id, gamespace_id)
        except DatabaseError as e:
            raise CurrencyError("Failed to update currency: " + e.args[1])


class CurrencyNotFound(Exception):
    pass


class PackAdapter(object):
    def __init__(self, record):
        self.pack_id = record["pack_id"]
        self.store_id = record["store_id"]
        self.name = record["pack_name"]
        self.product = record["pack_product"]
        self.prices = record["pack_prices"]
        self.type = record["pack_type"]


class PackComponentAdapter(object):
    def __init__(self, record):
        self.component_id = record["component_id"]
        self.name = record["component"]
        self.data = record["component_data"]


class PackComponentNotFound(Exception):
    pass


class PackModel(Model):
    PACK_TYPES = ["consumable", "nonconsumable", "subscription"]

    def __init__(self, db):
        self.db = db

    def get_setup_db(self):
        return self.db

    def get_setup_tables(self):
        return ["packs", "pack_components"]

    @coroutine
    def delete_pack(self, gamespace_id, pack_id):
        try:
            yield self.db.execute("""
                DELETE
                FROM `packs`
                WHERE `pack_id`=%s AND `gamespace_id`=%s;
            """, pack_id, gamespace_id)
        except DatabaseError as e:
            raise PackError("Failed to delete pack: " + e.args[1])

    @coroutine
    def delete_pack_component(self, gamespace_id, pack_id, component_id):
        try:
            yield self.db.execute("""
                DELETE
                FROM `pack_components`
                WHERE `pack_id`=%s AND `gamespace_id`=%s AND `component_id`=%s;
            """, pack_id, gamespace_id, component_id)
        except DatabaseError as e:
            raise PackError("Failed to delete pack component: " + e.args[1])

    @coroutine
    def find_pack(self, gamespace_id, store_id, pack_name):
        try:
            result = yield self.db.get("""
                SELECT *
                FROM `packs`
                WHERE `pack_name`=%s AND `store_id`=%s AND `gamespace_id`=%s;
            """, pack_name, store_id, gamespace_id)
        except DatabaseError as e:
            raise PackError("Failed to delete find pack: " + e.args[1])

        if result is None:
            raise PackNotFound()

        raise Return(PackAdapter(result))

    @coroutine
    def find_pack_component(self, gamespace_id, pack_id, component_name):
        try:
            result = yield self.db.get("""
                SELECT *
                FROM `pack_components`
                WHERE `pack_id`=%s AND `gamespace_id`=%s AND `component`=%s;
            """, pack_id, gamespace_id, component_name)
        except DatabaseError as e:
            raise PackError("Failed to find pack component: " + e.args[1])

        if result is None:
            raise PackComponentNotFound()

        raise Return(PackComponentAdapter(result))

    @coroutine
    def get_pack(self, gamespace_id, pack_id):
        try:
            result = yield self.db.get("""
                SELECT *
                FROM `packs`
                WHERE `pack_id`=%s AND `gamespace_id`=%s;
            """, pack_id, gamespace_id)
        except DatabaseError as e:
            raise PackError("Failed to get pack: " + e.args[1])

        if result is None:
            raise PackNotFound()

        raise Return(PackAdapter(result))

    @coroutine
    def get_pack_component(self, gamespace_id, pack_id, component_id):
        try:
            result = yield self.db.get("""
                SELECT *
                FROM `pack_components`
                WHERE `pack_id`=%s AND `gamespace_id`=%s AND `component_id`=%s;
            """, pack_id, gamespace_id, component_id)
        except DatabaseError as e:
            raise PackError("Failed to get pack component: " + e.args[1])

        if result is None:
            raise PackComponentNotFound()

        raise Return(PackComponentAdapter(result))

    @coroutine
    def list_pack_components(self, gamespace_id, pack_id):
        try:
            result = yield self.db.query("""
                SELECT *
                FROM `pack_components`
                WHERE `pack_id`=%s AND `gamespace_id`=%s;
            """, pack_id, gamespace_id)
        except DatabaseError as e:
            raise PackError("Failed to list pack components: " + e.args[1])
        else:
            raise Return(map(PackComponentAdapter, result))

    @coroutine
    def list_packs(self, gamespace_id, store_id):
        try:
            result = yield self.db.query("""
                SELECT *
                FROM `packs`
                WHERE `store_id`=%s AND `gamespace_id`=%s;
            """, store_id, gamespace_id)
        except DatabaseError as e:
            raise PackError("Failed to delete list packs: " + e.args[1])

        raise Return(map(PackAdapter, result))

    @coroutine
    def new_pack(self, gamespace_id, store_id, pack_name, pack_type, pack_product, pack_prices):

        try:
            yield self.find_pack(gamespace_id, store_id, pack_name)
        except PackNotFound:
            pass
        else:
            raise PackError("Pack '{0}' already exists is such store.".format(pack_name))

        try:
            pack_id = yield self.db.insert("""
                INSERT INTO `packs`
                (`gamespace_id`, `store_id`, `pack_name`, `pack_type`, `pack_product`, `pack_prices`)
                VALUES (%s, %s, %s, %s, %s, %s);
            """, gamespace_id, store_id, pack_name, pack_type, pack_product, ujson.dumps(pack_prices))
        except DatabaseError as e:
            raise PackError("Failed to add new pack: " + e.args[1])

        raise Return(pack_id)

    @coroutine
    def new_pack_component(self, gamespace_id, pack_id, component_name, component_data):
        if not isinstance(component_data, dict):
            raise PackError("Component data should be a dict")

        try:
            yield self.find_pack_component(gamespace_id, pack_id, component_name)
        except PackComponentNotFound:
            pass
        else:
            raise PackError("Pack component '{0}' already exists.".format(component_name))

        try:
            component_id = yield self.db.insert("""
                INSERT INTO `pack_components`
                (`gamespace_id`, `pack_id`, `component`, `component_data`)
                VALUES (%s, %s, %s, %s);
            """, gamespace_id, pack_id, component_name, ujson.dumps(component_data))
        except DatabaseError as e:
            raise PackError("Failed to add new pack component: " + e.args[1])

        raise Return(component_id)

    @coroutine
    def update_pack(self, gamespace_id, pack_id, pack_name, pack_type, pack_product, pack_prices):
        try:
            yield self.db.execute("""
                UPDATE `packs`
                SET `pack_name`=%s, `pack_product`=%s, `pack_prices`=%s, `pack_type`=%s
                WHERE `pack_id`=%s AND `gamespace_id`=%s;
            """, pack_name, pack_product, ujson.dumps(pack_prices), pack_type, pack_id, gamespace_id)
        except DatabaseError as e:
            raise PackError("Failed to update pack: " + e.args[1])

    @coroutine
    def update_pack_component(self, gamespace_id, pack_id, component_id, component_data):
        if not isinstance(component_data, dict):
            raise PackError("Component data should be a dict")

        try:
            yield self.get_pack_component(gamespace_id, pack_id, component_id)
        except PackComponentNotFound:
            raise PackError("Pack component not exists.")

        try:
            yield self.db.execute("""
                UPDATE `pack_components`
                SET `component_data`=%s
                WHERE `pack_id`=%s AND `gamespace_id`=%s AND `component_id`=%s;
            """, ujson.dumps(component_data), pack_id, gamespace_id, component_id)
        except DatabaseError as e:
            raise PackError("Failed to update pack component: " + e.args[1])


class PackError(Exception):
    pass


class PackNotFound(Exception):
    pass


