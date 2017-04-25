from tornado.gen import coroutine, Return

from common.database import DatabaseError
from common.model import Model
from common.validate import validate

import ujson


class CategoryAdapter(object):
    def __init__(self, record):
        self.category_id = record["category_id"]
        self.name = record["category_name"]
        self.public_item_scheme = record.get("category_public_item_scheme")
        self.private_item_scheme = record.get("category_private_item_scheme")


class CommonCategoryAdapter(object):
    def __init__(self, record):
        self.public_item_scheme = record.get("public_item_scheme")
        self.private_item_scheme = record.get("private_item_scheme")


class CategoryError(Exception):
    pass


class CategoryModel(Model):
    DEFAULT_PUBLIC_SCHEME = {
        "type": "object",
        "properties": {},
        "title": "Public part of the item, available to everyone"
    }

    DEFAULT_PRIVATE_SCHEME = {
        "type": "object",
        "properties": {},
        "title": "Private part of the item, available only after the purchase"
    }

    def __init__(self, db):
        self.db = db

    def get_setup_db(self):
        return self.db

    def get_setup_tables(self):
        return ["categories", "categories_common"]

    @coroutine
    @validate(gamespace_id="int", category_id="int")
    def delete_category(self, gamespace_id, category_id):
        try:
            yield self.db.execute("""
                DELETE
                FROM `categories`
                WHERE `category_id`=%s AND `gamespace_id`=%s;
            """, category_id, gamespace_id)
        except DatabaseError as e:
            raise CategoryError("Failed to delete category: " + e.args[1])

    @coroutine
    @validate(gamespace_id="int", category_name="str")
    def find_category(self, gamespace_id, category_name):
        try:
            result = yield self.db.get("""
                SELECT *
                FROM `categories`
                WHERE `category_name`=%s AND `gamespace_id`=%s;
            """, category_name, gamespace_id)
        except DatabaseError as e:
            raise CategoryError("Failed to find category: " + e.args[1])

        if result is None:
            raise CategoryNotFound()

        raise Return(CategoryAdapter(result))

    @coroutine
    @validate(gamespace_id="int", category_id="int")
    def get_category(self, gamespace_id, category_id):
        try:
            result = yield self.db.get("""
                SELECT *
                FROM `categories`
                WHERE `category_id`=%s AND `gamespace_id`=%s;
            """, category_id, gamespace_id)
        except DatabaseError as e:
            raise CategoryError("Failed to get category: " + e.args[1])

        if result is None:
            raise CategoryNotFound()

        raise Return(CategoryAdapter(result))

    @coroutine
    @validate(gamespace_id="int")
    def get_common_scheme(self, gamespace_id):
        try:
            result = yield self.db.get("""
                SELECT `public_item_scheme`, `private_item_scheme`
                FROM `categories_common`
                WHERE `gamespace_id`=%s;
            """, gamespace_id)
        except DatabaseError as e:
            raise CategoryError("Failed to get common scheme: " + e.args[1])

        if result is None:
            raise CategoryNotFound()

        raise Return(CommonCategoryAdapter(result))

    @coroutine
    @validate(gamespace_id="int")
    def list_categories(self, gamespace_id):
        try:
            result = yield self.db.query("""
                SELECT *
                FROM `categories`
                WHERE `gamespace_id`=%s;
            """, gamespace_id)
        except DatabaseError as e:
            raise CategoryError("Failed to list categories: " + e.args[1])

        raise Return(map(CategoryAdapter, result))

    @coroutine
    @validate(gamespace_id="int", category_name="str",
              category_public_item_scheme="json_dict",
              category_private_item_scheme="json_dict")
    def new_category(self, gamespace_id, category_name,
                     category_public_item_scheme,
                     category_private_item_scheme):

        try:
            yield self.find_category(gamespace_id, category_name)
        except CategoryNotFound:
            pass
        else:
            raise CategoryError("category '{0}' already exists.".format(category_name))

        try:
            result = yield self.db.insert(
                """
                    INSERT INTO `categories`
                    (`gamespace_id`, `category_name`, `category_public_item_scheme`, `category_private_item_scheme`)
                    VALUES (%s, %s, %s, %s);
                """, gamespace_id, category_name,
                ujson.dumps(category_public_item_scheme), ujson.dumps(category_private_item_scheme))
        except DatabaseError as e:
            raise CategoryError("Failed to add new category: " + e.args[1])

        raise Return(result)

    @coroutine
    @validate(gamespace_id="int", category_id="int", category_name="str",
              category_public_item_scheme="json_dict", category_private_item_scheme="json_dict")
    def update_category(self, gamespace_id, category_id, category_name,
                        category_public_item_scheme, category_private_item_scheme):
        try:
            yield self.db.execute(
                """
                    UPDATE `categories`
                    SET `category_name`=%s, `category_public_item_scheme`=%s, `category_private_item_scheme`=%s
                    WHERE `category_id`=%s AND `gamespace_id`=%s;
                """, category_name,
                ujson.dumps(category_public_item_scheme),
                ujson.dumps(category_private_item_scheme),
                category_id, gamespace_id)

        except DatabaseError as e:
            raise CategoryError("Failed to update category: " + e.args[1])

    @coroutine
    @validate(gamespace_id="int", public_item_scheme="json_dict", private_item_scheme="json_dict")
    def update_common_scheme(self, gamespace_id, public_item_scheme, private_item_scheme):

        public_item_scheme = ujson.dumps(public_item_scheme)
        private_item_scheme = ujson.dumps(private_item_scheme)

        try:
            yield self.db.insert("""
                INSERT INTO `categories_common`
                (`public_item_scheme`, `private_item_scheme`, `gamespace_id`)
                VALUES(%s, %s, %s)
                ON DUPLICATE KEY UPDATE
                `public_item_scheme`=%s, `private_item_scheme`=%s;
            """, public_item_scheme, private_item_scheme, gamespace_id, public_item_scheme, private_item_scheme)
        except DatabaseError as e:
            raise CategoryError("Failed to create a common scheme: " + e.args[1])


class CategoryNotFound(Exception):
    pass
