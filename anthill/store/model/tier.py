
from anthill.common.database import DatabaseError, DuplicateError
from anthill.common.model import Model
from anthill.common.validate import validate

import ujson


class CurrencyAdapter(object):
    def __init__(self, record):
        self.currency_id = record.get("currency_id")
        self.name = record.get("currency_name")
        self.title = record.get("currency_title")
        self.format = record.get("currency_format")
        self.symbol = record.get("currency_symbol")
        self.label = record.get("currency_label")


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

    async def delete_currency(self, gamespace_id, currency_id):
        try:
            await self.db.execute("""
                DELETE
                FROM `currencies`
                WHERE `currency_id`=%s AND `gamespace_id`=%s;
            """, currency_id, gamespace_id)
        except DatabaseError as e:
            raise CurrencyError("Failed to delete currency: " + e.args[1])

    async def find_currency(self, gamespace_id, currency_name):
        try:
            result = await self.db.get("""
                SELECT *
                FROM `currencies`
                WHERE `currency_name`=%s AND `gamespace_id`=%s;
            """, currency_name, gamespace_id)
        except DatabaseError as e:
            raise CurrencyError("Failed to find currency: " + e.args[1])

        if result is None:
            raise CurrencyNotFound()

        return CurrencyAdapter(result)

    async def get_currency(self, gamespace_id, currency_id):
        try:
            result = await self.db.get("""
                SELECT *
                FROM `currencies`
                WHERE `currency_id`=%s AND `gamespace_id`=%s;
            """, currency_id, gamespace_id)
        except DatabaseError as e:
            raise CurrencyError("Failed to get currency: " + e.args[1])

        if result is None:
            raise CurrencyNotFound()

        return CurrencyAdapter(result)

    async def list_currencies(self, gamespace_id, db=None):
        try:
            result = await (db or self.db).query("""
                SELECT *
                FROM `currencies`
                WHERE `gamespace_id`=%s;
            """, gamespace_id)
        except DatabaseError as e:
            raise CurrencyError("Failed to list currencies: " + e.args[1])

        return map(CurrencyAdapter, result)

    async def new_currency(self, gamespace_id, currency_name, currency_title, currency_format,
                     currency_symbol, currency_label):

        try:
            await self.find_currency(gamespace_id, currency_name)
        except CurrencyNotFound:
            pass
        else:
            raise TierError("Currency '{0}' already exists is such store.".format(currency_name))

        try:
            result = await self.db.insert("""
                INSERT INTO `currencies`
                (`gamespace_id`, `currency_name`, `currency_title`, `currency_format`, `currency_symbol`,
                `currency_label`)
                VALUES (%s, %s, %s, %s, %s, %s);
            """, gamespace_id, currency_name, currency_title, currency_format, currency_symbol, currency_label)
        except DatabaseError as e:
            raise CurrencyError("Failed to add new currency: " + e.args[1])

        return result

    async def update_currency(self, gamespace_id, currency_id, currency_name, currency_title, currency_format,
                        currency_symbol, currency_label):
        try:
            await self.db.execute("""
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
        self.tier_id = str(record.get("tier_id"))
        self.store_id = str(record.get("store_id"))
        self.name = record.get("tier_name")
        self.product = record.get("tier_product")
        self.title = record.get("tier_title")
        self.prices = record.get("tier_prices", {})


class TierComponentAdapter(object):
    def __init__(self, record):
        self.component_id = record.get("component_id")
        self.name = record.get("component")
        self.data = record.get("component_data")


class TierComponentNotFound(Exception):
    pass


class TierModel(Model):
    def __init__(self, db):
        self.db = db

    def get_setup_db(self):
        return self.db

    def get_setup_tables(self):
        return ["tiers", "tier_components"]

    async def delete_tier(self, gamespace_id, tier_id):
        try:
            await self.db.execute("""
                DELETE
                FROM `tiers`
                WHERE `tier_id`=%s AND `gamespace_id`=%s;
            """, tier_id, gamespace_id)
        except DatabaseError as e:
            raise TierError("Failed to delete tier: " + e.args[1])

    async def delete_tier_component(self, gamespace_id, tier_id, component_id):
        try:
            await self.db.execute("""
                DELETE
                FROM `tier_components`
                WHERE `tier_id`=%s AND `gamespace_id`=%s AND `component_id`=%s;
            """, tier_id, gamespace_id, component_id)
        except DatabaseError as e:
            raise TierError("Failed to delete tier component: " + e.args[1])

    async def find_tier(self, gamespace_id, store_id, tier_name):
        try:
            result = await self.db.get("""
                SELECT *
                FROM `tiers`
                WHERE `tier_name`=%s AND `store_id`=%s AND `gamespace_id`=%s;
            """, tier_name, store_id, gamespace_id)
        except DatabaseError as e:
            raise TierError("Failed to delete find tier: " + e.args[1])

        if result is None:
            raise TierNotFound()

        return TierAdapter(result)

    async def find_tier_component(self, gamespace_id, tier_id, component_name):
        try:
            result = await self.db.get("""
                SELECT *
                FROM `tier_components`
                WHERE `tier_id`=%s AND `gamespace_id`=%s AND `component`=%s;
            """, tier_id, gamespace_id, component_name)
        except DatabaseError as e:
            raise TierError("Failed to find tier component: " + e.args[1])

        if result is None:
            raise TierComponentNotFound()

        return TierComponentAdapter(result)

    async def get_tier(self, gamespace_id, tier_id, db=None):
        try:
            result = await (db or self.db).get("""
                SELECT *
                FROM `tiers`
                WHERE `tier_id`=%s AND `gamespace_id`=%s;
            """, tier_id, gamespace_id)
        except DatabaseError as e:
            raise TierError("Failed to get tier: " + e.args[1])

        if result is None:
            raise TierNotFound()

        return TierAdapter(result)

    async def get_tier_component(self, gamespace_id, tier_id, component_id):
        try:
            result = await self.db.get("""
                SELECT *
                FROM `tier_components`
                WHERE `tier_id`=%s AND `gamespace_id`=%s AND `component_id`=%s;
            """, tier_id, gamespace_id, component_id)
        except DatabaseError as e:
            raise TierError("Failed to get tier component: " + e.args[1])

        if result is None:
            raise TierComponentNotFound()

        return TierComponentAdapter(result)

    async def list_tier_components(self, gamespace_id, tier_id):
        try:
            result = await self.db.query("""
                SELECT *
                FROM `tier_components`
                WHERE `tier_id`=%s AND `gamespace_id`=%s;
            """, tier_id, gamespace_id)
        except DatabaseError as e:
            raise TierError("Failed to list tier components: " + e.args[1])
        else:
            return map(TierComponentAdapter, result)

    async def list_tiers(self, gamespace_id, store_id, db=None):
        try:
            result = await (db or self.db).query("""
                SELECT *
                FROM `tiers`
                WHERE `store_id`=%s AND `gamespace_id`=%s;
            """, store_id, gamespace_id)
        except DatabaseError as e:
            raise TierError("Failed to delete list tiers: " + e.args[1])

        return map(TierAdapter, result)

    @validate(gamespace_id="int", store_id="int", tier_name="str_name", tier_title="str", tier_product="str",
              tier_prices="json_dict_of_ints")
    async def new_tier(self, gamespace_id, store_id, tier_name, tier_title, tier_product, tier_prices):

        try:
            tier_id = await self.db.insert("""
                INSERT INTO `tiers`
                (`gamespace_id`, `store_id`, `tier_name`, `tier_title`, `tier_product`, `tier_prices`)
                VALUES (%s, %s, %s, %s, %s, %s);
            """, gamespace_id, store_id, tier_name, tier_title, tier_product, ujson.dumps(tier_prices))
        except DuplicateError:
            raise TierError("Tier with such name already exits in this store")
        except DatabaseError as e:
            raise TierError("Failed to add new tier: " + e.args[1])

        return tier_id

    async def new_tier_component(self, gamespace_id, tier_id, component_name, component_data):
        if not isinstance(component_data, dict):
            raise TierError("Component data should be a dict")

        try:
            await self.find_tier_component(gamespace_id, tier_id, component_name)
        except TierComponentNotFound:
            pass
        else:
            raise TierError("Tier component '{0}' already exists.".format(component_name))

        try:
            component_id = await self.db.insert("""
                INSERT INTO `tier_components`
                (`gamespace_id`, `tier_id`, `component`, `component_data`)
                VALUES (%s, %s, %s, %s);
            """, gamespace_id, tier_id, component_name, ujson.dumps(component_data))
        except DatabaseError as e:
            raise TierError("Failed to add new tier component: " + e.args[1])

        return component_id

    @validate(gamespace_id="int", tier_id="int", tier_name="str_name", tier_title="str", tier_product="str",
              tier_prices="json_dict_of_ints")
    async def update_tier(self, gamespace_id, tier_id, tier_name, tier_title, tier_product, tier_prices):

        try:
            await self.db.execute("""
                UPDATE `tiers`
                SET `tier_name`=%s, `tier_title`=%s, `tier_product`=%s, `tier_prices`=%s
                WHERE `tier_id`=%s AND `gamespace_id`=%s;
            """, tier_name, tier_title, tier_product, ujson.dumps(tier_prices), tier_id, gamespace_id)
        except DuplicateError:
            raise TierError("A tier with this name already exists in this store")
        except DatabaseError as e:
            raise TierError("Failed to update tier: " + e.args[1])

    async def update_tier_component(self, gamespace_id, tier_id, component_id, component_data):
        if not isinstance(component_data, dict):
            raise TierError("Component data should be a dict")

        try:
            await self.get_tier_component(gamespace_id, tier_id, component_id)
        except TierComponentNotFound:
            raise TierError("Tier component not exists.")

        try:
            await self.db.execute("""
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


