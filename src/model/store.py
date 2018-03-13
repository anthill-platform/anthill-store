
from tornado.gen import coroutine, Return, Future

from common.database import DatabaseError
from common.model import Model
from common.validate import validate

from item import ItemError
from campaign import CampaignError
from tier import CurrencyError

import ujson


class StoreAdapter(object):
    def __init__(self, data):
        self.store_id = data.get("store_id")
        self.name = data.get("store_name")
        self.campaign_scheme = data.get("store_campaign_scheme")


class StoreComponentAdapter(object):
    def __init__(self, data):
        self.store_id = data.get("store_id", None)
        self.component_id = data.get("component_id")
        self.name = data.get("component")
        self.data = data.get('component_data')


class StoreComponentNotFound(Exception):
    pass


class StoreModel(Model):
    def __init__(self, db, items, tiers, currencies, campaigns):
        self.db = db
        self.items = items
        self.tiers = tiers
        self.currencies = currencies
        self.campaigns = campaigns
        self.rc_cache = {}

    def get_setup_db(self):
        return self.db

    def get_setup_tables(self):
        return ["stores", "store_components"]

    @coroutine
    @validate(gamespace_id="int", store_id="int")
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
    @validate(gamespace_id="int", store_id="int", component_id="int")
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
    @validate(gamespace_id="int", store_name="str_name")
    def find_store(self, gamespace_id, store_name, db=None):
        try:
            result = yield (db or self.db).get("""
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
    @validate(gamespace_id="int", store_id="int", component_name="str_name")
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
    @validate(gamespace_id="int", store_name="str_name", component_name="str_name")
    def find_store_name_component(self, gamespace_id, store_name, component_name):
        try:
            result = yield self.db.get("""
                SELECT cmp.*, st.`store_id`
                FROM `store_components` AS cmp, `stores` AS st
                WHERE st.`store_name`=%s AND cmp.`gamespace_id`=%s AND cmp.`component`=%s
                  AND st.`store_id` = cmp.`store_id`;
            """, store_name, gamespace_id, component_name)
        except DatabaseError as e:
            raise StoreError("Failed to find store component: " + e.args[1])

        if result is None:
            raise StoreComponentNotFound()

        raise Return(StoreComponentAdapter(result))

    @coroutine
    @validate(gamespace_id="int", store_name="str_name", campaigns_extra_start_time="int",
              campaigns_extra_end_time="int")
    def build_store_data(self, gamespace_id, store_name,
                         campaigns_extra_start_time=0,
                         campaigns_extra_end_time=0):

        _key = "store_data:" + str(gamespace_id) + ":" + str(store_name) + ":" + \
            str(campaigns_extra_start_time) + ":" + str(campaigns_extra_end_time)

        existing_futures = self.rc_cache.get(_key, None)

        if existing_futures is not None:
            future = Future()
            existing_futures.append(future)
            result = yield future
            raise Return(result)

        new_futures = []
        self.rc_cache[_key] = new_futures

        def raise_(e):
            for f in new_futures:
                f.set_exception(e)
            del self.rc_cache[_key]
            raise e

        with (yield self.db.acquire()) as db:

            # look up the store itself
            store = yield self.find_store(gamespace_id, store_name, db=db)

            # gather the list of all currencies
            try:
                currencies_raw = yield self.currencies.list_currencies(gamespace_id, db=db)
            except CurrencyError as e:
                raise_(StoreError(e.message))
                return

            # get list of enabled items for certain store
            try:
                enabled_items_raw = yield self.items.list_enabled_items(gamespace_id, store.store_id, db=db)
            except ItemError as e:
                raise_(StoreError(e.message))
                return

            # prepare the dict of currencies
            currencies = {
                currency.name: currency
                for currency in currencies_raw
            }

            # outgoing items
            items = []
            tier_items = {}
            campaigns = {}

            # process the items fist
            for entry in enabled_items_raw:
                items.append({
                    "id": entry.item.name,
                    "category": entry.category.name,
                    "public": entry.item.public_data,
                    "billing": {
                        "type": "iap",
                        "tier": entry.tier.name
                    }
                })

                # since tiers are not requested separately, they are delivered together with items themselves
                # so they are extracted here
                if entry.tier.name not in tier_items:
                    tier_items[entry.tier.name] = entry.tier

            # process a list of items that are being under campaigns
            try:
                campaign_items_raw = yield self.campaigns.list_store_campaign_items(
                    gamespace_id, store.store_id,
                    campaigns_extra_start_time,
                    campaigns_extra_end_time)
            except CampaignError as e:
                raise_(StoreError(e.message))
                return

            for entry in campaign_items_raw:
                campaign_id = str(entry.campaign.campaign_id)
                campaign = campaigns.get(campaign_id, None)

                # this generates a list of campaigns, including campaign items
                if campaign is None:
                    campaign_items = {}
                    campaign = {
                        "payload": entry.campaign.data,
                        "time": {
                            "start": str(entry.campaign.time_start),
                            "end": str(entry.campaign.time_end)
                        },
                        "items": campaign_items
                    }
                    campaigns[campaign_id] = campaign
                else:
                    campaign_items = campaign["items"]

                campaign_items[entry.item_name] = {
                    "tier": entry.tier.name,
                    "public": entry.campaign_item.public_data
                }

                # since tiers are not requested separately, they are delivered together with campaign items themselves
                # so they are extracted here
                if entry.tier.name not in tier_items:
                    tier_items[entry.tier.name] = entry.tier

            # converts raw currency object into a JSON object
            def process_currency(currency_name, price):

                currency = currencies.get(currency_name)

                if not currency:
                    return {
                        "price": price
                    }

                return {
                    "title": currency.title,
                    "price": price,
                    "format": currency.format,
                    "symbol": currency.symbol,
                    "label": currency.label,
                }

            tiers = {
                tier_name: {
                    "product": tier.product,
                    "prices": {
                        currency: process_currency(currency, price)
                        for currency, price in tier.prices.iteritems()
                    }
                } for tier_name, tier in tier_items.iteritems()
            }

            result = {
                "items": items,
                "tiers": tiers,
                "campaigns": campaigns.values()
            }

            for f in new_futures:
                f.set_result(result)
            del self.rc_cache[_key]

            raise Return(result)

    @coroutine
    @validate(gamespace_id="int", store_id="int")
    def get_store(self, gamespace_id, store_id, db=None):
        try:
            result = yield (db or self.db).get("""
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
    @validate(gamespace_id="int", store_id="int", component_id="int")
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
    @validate(gamespace_id="int", store_id="int")
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
    @validate(gamespace_id="int")
    def list_stores(self, gamespace_id):
        result = yield self.db.query("""
            SELECT `store_name`, `store_id`
            FROM `stores`
            WHERE `gamespace_id`=%s;
        """, gamespace_id)

        raise Return(map(StoreAdapter, result))

    @coroutine
    @validate(gamespace_id="int", store_name="str_name", campaign_scheme="json_dict")
    def new_store(self, gamespace_id, store_name, campaign_scheme):

        try:
            yield self.find_store(gamespace_id, store_name)
        except StoreNotFound:
            pass
        else:
            raise StoreError("Store '{0}' already exists.".format(store_name))

        try:
            store_id = yield self.db.insert("""
                INSERT INTO `stores`
                (`gamespace_id`, `store_name`, `campaign_scheme`)
                VALUES (%s, %s, %s);
            """, gamespace_id, store_name, ujson.dumps(campaign_scheme))
        except DatabaseError as e:
            raise StoreError("Failed to add new store: " + e.args[1])

        raise Return(store_id)

    @coroutine
    @validate(gamespace_id="int", store_id="int", component_name="str_name", component_data="json_dict")
    def new_store_component(self, gamespace_id, store_id, component_name, component_data):

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
    @validate(gamespace_id="int", store_id="int", store_name="str", store_campaign_scheme="json_dict")
    def update_store(self, gamespace_id, store_id, store_name, store_campaign_scheme):
        try:
            yield self.db.execute("""
                UPDATE `stores`
                SET `store_name`=%s, `store_campaign_scheme`=%s
                WHERE `store_id`=%s AND `gamespace_id`=%s;
            """, store_name, ujson.dumps(store_campaign_scheme), store_id, gamespace_id)
        except DatabaseError as e:
            raise StoreError("Failed to update store: " + e.args[1])

    @coroutine
    @validate(gamespace_id="int", store_id="int", component_id="int", component_data="json_dict")
    def update_store_component(self, gamespace_id, store_id, component_id, component_data):

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
