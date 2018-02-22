from tornado.gen import coroutine, Return

from common.database import DatabaseError, DuplicateError
from common.model import Model
from common.validate import validate
from category import CategoryAdapter

from tier import TierAdapter

import ujson


class StoreItemAdapter(object):
    def __init__(self, record):
        self.item_id = str(record.get("item_id"))
        self.name = record.get("item_name")
        self.store_id = str(record.get("store_id"))
        self.public_data = record.get("item_public_data")
        self.private_data = record.get("item_private_data")
        self.category = record.get("item_category")
        self.tier = str(record.get("item_tier"))
        self.enabled = bool(record.get("item_enabled"))

    def description(self, language):
        descriptions = self.public_data.get("description", {})

        if isinstance(descriptions, (str, unicode)):
            return descriptions
        elif isinstance(descriptions, dict):
            return descriptions.get(language, descriptions.get("EN", "Unknown"))

        return "Unknown"

    def title(self, language):
        titles = self.public_data.get("title", {})

        if isinstance(titles, (str, unicode)):
            return titles
        elif isinstance(titles, dict):
            return titles.get(language, titles.get("EN", "Unknown"))

        return "Unknown"

    def apply_campaign(self, campaign_item):
        self.public_data = campaign_item.public_data
        self.private_data = campaign_item.private_data
        self.tier = campaign_item.tier


class StoreItemCategoryAdapter(StoreItemAdapter):
    def __init__(self, record):
        super(StoreItemCategoryAdapter, self).__init__(record)
        self.category = CategoryAdapter(record)


class ItemTierCategoryAdapter(object):
    def __init__(self, data):
        self.item = StoreItemAdapter(data)
        self.tier = TierAdapter(data)
        self.category = CategoryAdapter(data)


class ItemError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


class ItemModel(Model):
    def __init__(self, db):
        self.db = db

    def get_setup_tables(self):
        return ["items"]

    def get_setup_db(self):
        return self.db

    @coroutine
    @validate(gamespace_id="int", item_id="int")
    def delete_item(self, gamespace_id, item_id):
        try:
            yield self.db.execute("""
                DELETE
                FROM `orders`
                WHERE `item_id`=%s AND `gamespace_id`=%s;
            """, item_id, gamespace_id)

            yield self.db.execute("""
                DELETE
                FROM `items`
                WHERE `item_id`=%s AND `gamespace_id`=%s;
            """, item_id, gamespace_id)
        except DatabaseError as e:
            raise ItemError("Failed to delete item: " + e.args[1])

    @coroutine
    @validate(gamespace_id="int", store_id="int", item_name="str")
    def find_item(self, gamespace_id, store_id, item_name):
        try:
            result = yield self.db.get("""
                SELECT *
                FROM `items`
                WHERE `item_name`=%s AND `store_id`=%s AND `gamespace_id`=%s;
            """, item_name, store_id, gamespace_id)
        except DatabaseError as e:
            raise ItemError("Failed to find item: " + e.args[1])

        if result is None:
            raise ItemNotFound()

        raise Return(StoreItemAdapter(result))

    @coroutine
    @validate(gamespace_id="int", item_id="int")
    def get_item(self, gamespace_id, item_id, db=None):
        try:
            result = yield (db or self.db).get("""
                SELECT *
                FROM `items`
                WHERE `item_id`=%s AND `gamespace_id`=%s;
            """, item_id, gamespace_id)
        except DatabaseError as e:
            raise ItemError("Failed to get item: " + e.args[1])

        if result is None:
            raise ItemNotFound()

        raise Return(StoreItemAdapter(result))

    @coroutine
    @validate(gamespace_id="int", store_id="int")
    def list_items(self, gamespace_id, store_id, db=None):
        try:
            result = yield (db or self.db).query("""
                SELECT 
                    `items`.`item_id`, 
                    `items`.`item_name`, 
                    `items`.`item_public_data`, 
                    `items`.`item_enabled`,
                    `tiers`.`tier_name`, 
                    `tiers`.`tier_title`, 
                    `tiers`.`tier_id`, 
                    `tiers`.`tier_product`, 
                    `tiers`.`tier_prices`, 
                    `categories`.`category_id`,
                    `categories`.`category_name`
                FROM `items`, `tiers`, `categories`
                WHERE
                `items`.`gamespace_id`=%s AND
                `items`.`store_id`=%s AND
                `items`.`item_category`=`categories`.`category_id` AND
                `tiers`.`tier_id`=`items`.`item_tier`
                ORDER BY `items`.`item_id` ASC;
            """, gamespace_id, store_id)
        except DatabaseError as e:
            raise ItemError("Failed to find store data: " + e.args[1])

        raise Return(map(ItemTierCategoryAdapter, result))

    @coroutine
    @validate(gamespace_id="int", store_id="int")
    def list_enabled_items(self, gamespace_id, store_id, db=None):
        try:
            result = yield (db or self.db).query("""
                SELECT 
                    `items`.`item_id`, 
                    `items`.`item_name`, 
                    `items`.`item_public_data`, 
                    `items`.`item_enabled`,
                    `tiers`.`tier_name`, 
                    `tiers`.`tier_title`, 
                    `tiers`.`tier_id`, 
                    `tiers`.`tier_product`, 
                    `tiers`.`tier_prices`, 
                    `categories`.`category_id`,
                    `categories`.`category_name`
                FROM `items`, `tiers`, `categories`
                WHERE
                `items`.`gamespace_id`=%s AND
                `items`.`store_id`=%s AND
                `items`.`item_enabled`=1 AND
                `items`.`item_category`=`categories`.`category_id` AND
                `tiers`.`tier_id`=`items`.`item_tier`
                ORDER BY `items`.`item_id` ASC;
            """, gamespace_id, store_id)
        except DatabaseError as e:
            raise ItemError("Failed to find store data: " + e.args[1])

        raise Return(map(ItemTierCategoryAdapter, result))

    @coroutine
    @validate(gamespace_id="int", store_id="int", category_id="int", item_name="str",
              item_enabled="bool", item_public_data="json", item_private_data="json", item_tier="int")
    def new_item(self, gamespace_id, store_id, category_id, item_name, item_enabled,
                 item_public_data, item_private_data, item_tier):
        try:
            item_id = yield self.db.insert(
                """
                    INSERT INTO `items`
                    (`gamespace_id`, `store_id`, `item_category`, `item_name`,
                        `item_enabled`, `item_public_data`, `item_private_data`, `item_tier`)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                """, gamespace_id, store_id, category_id, item_name, int(item_enabled),
                ujson.dumps(item_public_data), ujson.dumps(item_private_data), item_tier)
        except DuplicateError:
            raise ItemError("Item '{0}' already exists is such store.".format(item_name))
        except DatabaseError as e:
            raise ItemError("Failed to add new item: " + e.args[1])

        raise Return(item_id)

    @coroutine
    @validate(gamespace_id="int", item_id="int", item_name="str", item_enabled="bool",
              item_public_data="json", item_private_data="json", item_tier="int")
    def update_item(self, gamespace_id, item_id, item_name, item_enabled,
                    item_public_data, item_private_data, item_tier):

        try:
            yield self.db.execute("""
                UPDATE `items`
                SET `item_name`=%s, `item_enabled`=%s, 
                    `item_public_data`=%s, `item_private_data`=%s, `item_tier`=%s
                WHERE `item_id`=%s AND `gamespace_id`=%s;
            """, item_name, int(item_enabled), ujson.dumps(item_public_data),
            ujson.dumps(item_private_data), item_tier, item_id, gamespace_id)
        except DuplicateError:
            raise ItemError("An item with that name already exists")
        except DatabaseError as e:
            raise ItemError("Failed to update item: " + e.args[1])


class ItemNotFound(Exception):
    pass
