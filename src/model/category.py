
from tornado.gen import coroutine, Return

from common.database import DatabaseError
from common.model import Model
import ujson


class CategoryAdapter(object):
    def __init__(self, record):
        self.category_id = record["category_id"]
        self.name = record["category_name"]
        self.scheme = record.get("category_scheme")


class CategoryError(Exception):
    pass


class CategoryModel(Model):
    def __init__(self, db):
        self.db = db

    def get_setup_db(self):
        return self.db

    def get_setup_tables(self):
        return ["categories", "categories_common"]

    @coroutine
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
    def get_common_scheme(self, gamespace_id):
        try:
            result = yield self.db.get("""
                SELECT `category_scheme`
                FROM `categories_common`
                WHERE `gamespace_id`=%s;
            """, gamespace_id)
        except DatabaseError as e:
            raise CategoryError("Failed to get common scheme: " + e.args[1])

        if result is None:
            raise CategoryNotFound()

        raise Return(result["category_scheme"])

    @coroutine
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
    def new_category(self, gamespace_id, category_name, category_scheme):

        try:
            yield self.find_category(gamespace_id, category_name)
        except CategoryNotFound:
            pass
        else:
            raise CategoryError("category '{0}' already exists.".format(category_name))

        try:
            result = yield self.db.insert("""
                INSERT INTO `categories`
                (`gamespace_id`, `category_name`, `category_scheme`)
                VALUES (%s, %s, %s);
            """, gamespace_id, category_name, ujson.dumps(category_scheme))
        except DatabaseError as e:
            raise CategoryError("Failed to add new category: " + e.args[1])

        raise Return(result)

    @coroutine
    def update_category(self, gamespace_id, category_id, category_name, category_scheme):
        try:
            yield self.db.execute("""
                UPDATE `categories`
                SET `category_name`=%s, `category_scheme`=%s
                WHERE `category_id`=%s AND `gamespace_id`=%s;
            """, category_name, ujson.dumps(category_scheme), category_id, gamespace_id)
        except DatabaseError as e:
            raise CategoryError("Failed to update category: " + e.args[1])

    @coroutine
    def update_common_scheme(self, gamespace_id, scheme):

        try:
            yield self.get_common_scheme(gamespace_id)
        except CategoryNotFound:
            try:
                yield self.db.insert("""
                    INSERT INTO `categories_common`
                    (`category_scheme`, `gamespace_id`)
                    VALUES(%s, %s);
                """, ujson.dumps(scheme), gamespace_id)
            except DatabaseError as e:
                raise CategoryError("Failed to create a common scheme: " + e.args[1])
        else:
            try:
                yield self.db.execute("""
                    UPDATE `categories_common`
                    SET `category_scheme`=%s
                    WHERE `gamespace_id`=%s;
                """, ujson.dumps(scheme), gamespace_id)
            except DatabaseError as e:
                raise CategoryError("Failed to update common scheme: " + e.args[1])


class CategoryNotFound(Exception):
    pass
