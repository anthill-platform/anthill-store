
from tornado.gen import coroutine, Return

from common.database import DatabaseError
from common.model import Model
import ujson


class CurrencyAdapter(object):
    def __init__(self, record):
        self.currency_id = record["currency_id"]
        self.name = record["currency_name"]
        self.title = record["currency_title"]
        self.format = record["currency_format"]
        self.symbol = record["currency_symbol"]
        self.label = record["currency_label"]


class CurrencyError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


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
            raise CurrencyError("Failed to delete currency: " + e.args[1])

    @coroutine
    def find_currency(self, gamespace_id, currency_name):
        try:
            result = yield self.db.get("""
                SELECT *
                FROM `currencies`
                WHERE `currency_name`=%s AND `gamespace_id`=%s;
            """, currency_name, gamespace_id)
        except DatabaseError as e:
            raise CurrencyError("Failed to find currency: " + e.args[1])

        if result is None:
            raise CurrencyNotFound()

        raise Return(CurrencyAdapter(result))

    @coroutine
    def get_currency(self, gamespace_id, currency_id):
        try:
            result = yield self.db.get("""
                SELECT *
                FROM `currencies`
                WHERE `currency_id`=%s AND `gamespace_id`=%s;
            """, currency_id, gamespace_id)
        except DatabaseError as e:
            raise CurrencyError("Failed to get currency: " + e.args[1])

        if result is None:
            raise CurrencyNotFound()

        raise Return(CurrencyAdapter(result))

    @coroutine
    def list_currencies(self, gamespace_id):
        try:
            result = yield self.db.query("""
                SELECT *
                FROM `currencies`
                WHERE `gamespace_id`=%s;
            """, gamespace_id)
        except DatabaseError as e:
            raise CurrencyError("Failed to list currencies: " + e.args[1])

        raise Return(map(CurrencyAdapter, result))

    @coroutine
    def new_currency(self, gamespace_id, currency_name, currency_title, currency_format,
                     currency_symbol, currency_label):

        try:
            yield self.find_currency(gamespace_id, currency_name)
        except CurrencyNotFound:
            pass
        else:
            raise TierError("Currency '{0}' already exists is such store.".format(currency_name))

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


class TierAdapter(object):
    def __init__(self, record):
        self.tier_id = record["tier_id"]
        self.store_id = record["store_id"]
        self.name = record["tier_name"]
        self.product = record["tier_product"]
        self.prices = record["tier_prices"]


class TierComponentAdapter(object):
    def __init__(self, record):
        self.component_id = record["component_id"]
        self.name = record["component"]
        self.data = record["component_data"]


class TierComponentNotFound(Exception):
    pass


class TierModel(Model):
    def __init__(self, db):
        self.db = db

    def get_setup_db(self):
        return self.db

    def get_setup_tables(self):
        return ["tiers", "tier_components"]

    @coroutine
    def delete_tier(self, gamespace_id, tier_id):
        try:
            yield self.db.execute("""
                DELETE
                FROM `tiers`
                WHERE `tier_id`=%s AND `gamespace_id`=%s;
            """, tier_id, gamespace_id)
        except DatabaseError as e:
            raise TierError("Failed to delete tier: " + e.args[1])

    @coroutine
    def delete_tier_component(self, gamespace_id, tier_id, component_id):
        try:
            yield self.db.execute("""
                DELETE
                FROM `tier_components`
                WHERE `tier_id`=%s AND `gamespace_id`=%s AND `component_id`=%s;
            """, tier_id, gamespace_id, component_id)
        except DatabaseError as e:
            raise TierError("Failed to delete tier component: " + e.args[1])

    @coroutine
    def find_tier(self, gamespace_id, store_id, tier_name):
        try:
            result = yield self.db.get("""
                SELECT *
                FROM `tiers`
                WHERE `tier_name`=%s AND `store_id`=%s AND `gamespace_id`=%s;
            """, tier_name, store_id, gamespace_id)
        except DatabaseError as e:
            raise TierError("Failed to delete find tier: " + e.args[1])

        if result is None:
            raise TierNotFound()

        raise Return(TierAdapter(result))

    @coroutine
    def find_tier_component(self, gamespace_id, tier_id, component_name):
        try:
            result = yield self.db.get("""
                SELECT *
                FROM `tier_components`
                WHERE `tier_id`=%s AND `gamespace_id`=%s AND `component`=%s;
            """, tier_id, gamespace_id, component_name)
        except DatabaseError as e:
            raise TierError("Failed to find tier component: " + e.args[1])

        if result is None:
            raise TierComponentNotFound()

        raise Return(TierComponentAdapter(result))

    @coroutine
    def get_tier(self, gamespace_id, tier_id):
        try:
            result = yield self.db.get("""
                SELECT *
                FROM `tiers`
                WHERE `tier_id`=%s AND `gamespace_id`=%s;
            """, tier_id, gamespace_id)
        except DatabaseError as e:
            raise TierError("Failed to get tier: " + e.args[1])

        if result is None:
            raise TierNotFound()

        raise Return(TierAdapter(result))

    @coroutine
    def get_tier_component(self, gamespace_id, tier_id, component_id):
        try:
            result = yield self.db.get("""
                SELECT *
                FROM `tier_components`
                WHERE `tier_id`=%s AND `gamespace_id`=%s AND `component_id`=%s;
            """, tier_id, gamespace_id, component_id)
        except DatabaseError as e:
            raise TierError("Failed to get tier component: " + e.args[1])

        if result is None:
            raise TierComponentNotFound()

        raise Return(TierComponentAdapter(result))

    @coroutine
    def list_tier_components(self, gamespace_id, tier_id):
        try:
            result = yield self.db.query("""
                SELECT *
                FROM `tier_components`
                WHERE `tier_id`=%s AND `gamespace_id`=%s;
            """, tier_id, gamespace_id)
        except DatabaseError as e:
            raise TierError("Failed to list tier components: " + e.args[1])
        else:
            raise Return(map(TierComponentAdapter, result))

    @coroutine
    def list_tiers(self, gamespace_id, store_id):
        try:
            result = yield self.db.query("""
                SELECT *
                FROM `tiers`
                WHERE `store_id`=%s AND `gamespace_id`=%s;
            """, store_id, gamespace_id)
        except DatabaseError as e:
            raise TierError("Failed to delete list tiers: " + e.args[1])

        raise Return(map(TierAdapter, result))

    @coroutine
    def new_tier(self, gamespace_id, store_id, tier_name, tier_product, tier_prices):

        try:
            yield self.find_tier(gamespace_id, store_id, tier_name)
        except TierNotFound:
            pass
        else:
            raise TierError("Tier '{0}' already exists is such store.".format(tier_name))

        try:
            tier_id = yield self.db.insert("""
                INSERT INTO `tiers`
                (`gamespace_id`, `store_id`, `tier_name`, `tier_product`, `tier_prices`)
                VALUES (%s, %s, %s, %s, %s);
            """, gamespace_id, store_id, tier_name, tier_product, ujson.dumps(tier_prices))
        except DatabaseError as e:
            raise TierError("Failed to add new tier: " + e.args[1])

        raise Return(tier_id)

    @coroutine
    def new_tier_component(self, gamespace_id, tier_id, component_name, component_data):
        if not isinstance(component_data, dict):
            raise TierError("Component data should be a dict")

        try:
            yield self.find_tier_component(gamespace_id, tier_id, component_name)
        except TierComponentNotFound:
            pass
        else:
            raise TierError("Tier component '{0}' already exists.".format(component_name))

        try:
            component_id = yield self.db.insert("""
                INSERT INTO `tier_components`
                (`gamespace_id`, `tier_id`, `component`, `component_data`)
                VALUES (%s, %s, %s, %s);
            """, gamespace_id, tier_id, component_name, ujson.dumps(component_data))
        except DatabaseError as e:
            raise TierError("Failed to add new tier component: " + e.args[1])

        raise Return(component_id)

    @coroutine
    def update_tier(self, gamespace_id, tier_id, tier_name, tier_product, tier_prices):
        try:
            yield self.db.execute("""
                UPDATE `tiers`
                SET `tier_name`=%s, `tier_product`=%s, `tier_prices`=%s
                WHERE `tier_id`=%s AND `gamespace_id`=%s;
            """, tier_name, tier_product, ujson.dumps(tier_prices), tier_id, gamespace_id)
        except DatabaseError as e:
            raise TierError("Failed to update tier: " + e.args[1])

    @coroutine
    def update_tier_component(self, gamespace_id, tier_id, component_id, component_data):
        if not isinstance(component_data, dict):
            raise TierError("Component data should be a dict")

        try:
            yield self.get_tier_component(gamespace_id, tier_id, component_id)
        except TierComponentNotFound:
            raise TierError("Tier component not exists.")

        try:
            yield self.db.execute("""
                UPDATE `tier_components`
                SET `component_data`=%s
                WHERE `tier_id`=%s AND `gamespace_id`=%s AND `component_id`=%s;
            """, ujson.dumps(component_data), tier_id, gamespace_id, component_id)
        except DatabaseError as e:
            raise TierError("Failed to update tier component: " + e.args[1])


class TierError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


class TierNotFound(Exception):
    pass


