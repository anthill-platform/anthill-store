from tornado.gen import coroutine, Return

from common.database import DatabaseError
from common.model import Model
from common.validate import validate
from category import CategoryAdapter

import common
import ujson


class ItemAdapter(object):
    def __init__(self, record):
        self.item_id = record["item_id"]
        self.name = record["item_name"]
        self.store_id = record["store_id"]
        self.data = record.get("item_json")
        self.category = record["item_category"]
        self.method = record["item_method"]
        self.method_data = record["item_method_data"]

    def description(self, language):
        descriptions = self.data.get("description", {})

        if isinstance(descriptions, (str, unicode)):
            return descriptions
        elif isinstance(descriptions, dict):
            return descriptions.get(language, descriptions.get("EN", "Unknown"))

        return "Unknown"

    def title(self, language):
        titles = self.data.get("title", {})

        if isinstance(titles, (str, unicode)):
            return titles
        elif isinstance(titles, dict):
            return titles.get(language, titles.get("EN", "Unknown"))

        return "Unknown"


class ItemCategoryAdapter(ItemAdapter):
    def __init__(self, record):
        super(ItemCategoryAdapter, self).__init__(record)
        self.category = CategoryAdapter(record)


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

        raise Return(ItemAdapter(result))

    @coroutine
    @validate(gamespace_id="int", item_id="int")
    def get_item(self, gamespace_id, item_id):
        try:
            result = yield self.db.get("""
                SELECT *
                FROM `items`
                WHERE `item_id`=%s AND `gamespace_id`=%s;
            """, item_id, gamespace_id)
        except DatabaseError as e:
            raise ItemError("Failed to get item: " + e.args[1])

        if result is None:
            raise ItemNotFound()

        raise Return(ItemAdapter(result))

    @coroutine
    @validate(gamespace_id="int", store_id="int")
    def list_items(self, gamespace_id, store_id):
        try:
            result = yield self.db.query("""
                SELECT *
                FROM `items` i JOIN `categories` c
                WHERE i.`store_id`=%s AND i.`gamespace_id`=%s AND i.`item_category`=c.`category_id`;
            """, store_id, gamespace_id)
        except DatabaseError as e:
            raise ItemError("Failed to list items: " + e.args[1])

        raise Return(map(ItemCategoryAdapter, result))

    @coroutine
    @validate(gamespace_id="int", store_id="int", category_id="int", item_name="str",
              item_data="json", item_method="str_name", method_data="json")
    def new_item(self, gamespace_id, store_id, category_id, item_name,
                 item_data, item_method, method_data):

        try:
            yield self.find_item(gamespace_id, store_id, item_name)
        except ItemNotFound:
            pass
        else:
            raise ItemError("Item '{0}' already exists is such store.".format(item_name))

        try:
            item_id = yield self.db.insert(
                """
                    INSERT INTO `items`
                    (`gamespace_id`, `store_id`, `item_category`, `item_name`,
                        `item_json`, `item_method`, `item_method_data`)
                    VALUES (%s, %s, %s, %s, %s, %s, %s);
                """, gamespace_id, store_id, category_id, item_name,
                ujson.dumps(item_data), item_method, ujson.dumps(method_data))
        except DatabaseError as e:
            raise ItemError("Failed to add new item: " + e.args[1])

        raise Return(item_id)

    @coroutine
    @validate(gamespace_id="int", item_id="int", item_name="str", item_data="json")
    def update_item(self, gamespace_id, item_id, item_name, item_data):

        try:
            yield self.db.execute("""
                UPDATE `items`
                SET `item_name`=%s, `item_json`=%s
                WHERE `item_id`=%s AND `gamespace_id`=%s;
            """, item_name, ujson.dumps(item_data), item_id, gamespace_id)
        except DatabaseError as e:
            raise ItemError("Failed to update item: " + e.args[1])

    @coroutine
    @validate(gamespace_id="int", item_id="int", method_data="json")
    def update_item_billing(self, gamespace_id, item_id, method_data):
        try:
            yield self.db.execute("""
                UPDATE `items`
                SET `item_method_data`=%s
                WHERE `item_id`=%s AND `gamespace_id`=%s;
            """, ujson.dumps(method_data), item_id, gamespace_id)
        except DatabaseError as e:
            raise ItemError("Failed to update item billing: " + e.args[1])


class ItemNotFound(Exception):
    pass
