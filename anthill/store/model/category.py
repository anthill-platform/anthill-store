
from anthill.common.database import DatabaseError
from anthill.common.model import Model
from anthill.common.validate import validate

import ujson


class CategoryAdapter(object):
    def __init__(self, record):
        self.category_id = record.get("category_id")
        self.name = record.get("category_name")
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

    @validate(gamespace_id="int", category_id="int")
    async def delete_category(self, gamespace_id, category_id):
        try:
            await self.db.execute("""
                DELETE
                FROM `categories`
                WHERE `category_id`=%s AND `gamespace_id`=%s;
            """, category_id, gamespace_id)
        except DatabaseError as e:
            raise CategoryError("Failed to delete category: " + e.args[1])

    @validate(gamespace_id="int", category_name="str")
    async def find_category(self, gamespace_id, category_name):
        try:
            result = await self.db.get("""
                SELECT *
                FROM `categories`
                WHERE `category_name`=%s AND `gamespace_id`=%s;
            """, category_name, gamespace_id)
        except DatabaseError as e:
            raise CategoryError("Failed to find category: " + e.args[1])

        if result is None:
            raise CategoryNotFound()

        return CategoryAdapter(result)

    @validate(gamespace_id="int", category_id="int")
    async def get_category(self, gamespace_id, category_id, db=None):
        try:
            result = await (db or self.db).get("""
                SELECT *
                FROM `categories`
                WHERE `category_id`=%s AND `gamespace_id`=%s;
            """, category_id, gamespace_id)
        except DatabaseError as e:
            raise CategoryError("Failed to get category: " + e.args[1])

        if result is None:
            raise CategoryNotFound()

        return CategoryAdapter(result)

    @validate(gamespace_id="int")
    async def get_common_scheme(self, gamespace_id):
        try:
            result = await self.db.get("""
                SELECT `public_item_scheme`, `private_item_scheme`
                FROM `categories_common`
                WHERE `gamespace_id`=%s;
            """, gamespace_id)
        except DatabaseError as e:
            raise CategoryError("Failed to get common scheme: " + e.args[1])

        if result is None:
            raise CategoryNotFound()

        return CommonCategoryAdapter(result)

    @validate(gamespace_id="int")
    async def list_categories(self, gamespace_id):
        try:
            result = await self.db.query("""
                SELECT *
                FROM `categories`
                WHERE `gamespace_id`=%s;
            """, gamespace_id)
        except DatabaseError as e:
            raise CategoryError("Failed to list categories: " + e.args[1])

        return map(CategoryAdapter, result)

    @validate(gamespace_id="int", category_name="str",
              category_public_item_scheme="json_dict",
              category_private_item_scheme="json_dict")
    async def new_category(self, gamespace_id, category_name,
                     category_public_item_scheme,
                     category_private_item_scheme):

        try:
            await self.find_category(gamespace_id, category_name)
        except CategoryNotFound:
            pass
        else:
            raise CategoryError("category '{0}' already exists.".format(category_name))

        try:
            result = await self.db.insert(
                """
                    INSERT INTO `categories`
                    (`gamespace_id`, `category_name`, `category_public_item_scheme`, `category_private_item_scheme`)
                    VALUES (%s, %s, %s, %s);
                """, gamespace_id, category_name,
                ujson.dumps(category_public_item_scheme), ujson.dumps(category_private_item_scheme))
        except DatabaseError as e:
            raise CategoryError("Failed to add new category: " + e.args[1])

        return result

    @validate(gamespace_id="int", category_id="int", category_name="str",
              category_public_item_scheme="json_dict", category_private_item_scheme="json_dict")
    async def update_category(self, gamespace_id, category_id, category_name,
                        category_public_item_scheme, category_private_item_scheme):
        try:
            await self.db.execute(
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

    @validate(gamespace_id="int", public_item_scheme="json_dict", private_item_scheme="json_dict")
    async def update_common_scheme(self, gamespace_id, public_item_scheme, private_item_scheme):

        public_item_scheme = ujson.dumps(public_item_scheme)
        private_item_scheme = ujson.dumps(private_item_scheme)

        try:
            await self.db.insert("""
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
