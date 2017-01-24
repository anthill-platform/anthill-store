
from tornado.gen import coroutine, Return

from common.database import DatabaseError
from common.model import Model
from common.validate import validate

import ujson


class ContentAdapter(object):
    def __init__(self, record):
        self.content_id = record.get("content_id")
        self.name = record.get("content_name", "")
        self.data = record.get("content_json", {})


class ContentError(Exception):
    pass


class ContentModel(Model):
    def __init__(self, db):
        self.db = db

    def get_setup_db(self):
        return self.db

    def get_setup_tables(self):
        return ["contents"]

    @coroutine
    @validate(gamespace_id="int", content_id="int")
    def delete_content(self, gamespace_id, content_id):
        try:
            yield self.db.execute("""
                DELETE
                FROM `contents`
                WHERE `content_id`=%s AND `gamespace_id`=%s;
            """, content_id, gamespace_id)
        except DatabaseError as e:
            raise ContentError("Failed to delete content: " + e.args[1])

    @coroutine
    @validate(gamespace_id="int", content_name="str")
    def find_content(self, gamespace_id, content_name):
        try:
            result = yield self.db.get("""
                SELECT *
                FROM `contents`
                WHERE `content_name`=%s AND `gamespace_id`=%s;
            """, content_name, gamespace_id)
        except DatabaseError as e:
            raise ContentError("Failed to find content: " + e.args[1])

        if result is None:
            raise ContentNotFound()

        raise Return(ContentAdapter(result))

    @coroutine
    @validate(gamespace_id="int", content_id="int")
    def get_content(self, gamespace_id, content_id):
        try:
            result = yield self.db.get("""
                SELECT *
                FROM `contents`
                WHERE `content_id`=%s AND `gamespace_id`=%s;
            """, content_id, gamespace_id)
        except DatabaseError as e:
            raise ContentError("Failed to get content: " + e.args[1])

        if result is None:
            raise ContentNotFound()

        raise Return(ContentAdapter(result))

    @coroutine
    @validate(gamespace_id="int")
    def list_contents(self, gamespace_id):
        try:
            result = yield self.db.query("""
                SELECT *
                FROM `contents`
                WHERE `gamespace_id`=%s;
            """, gamespace_id)
        except DatabaseError as e:
            raise ContentError("Failed to list contents: " + e.args[1])

        raise Return(map(ContentAdapter, result))

    @coroutine
    @validate(gamespace_id="int", content_name="str", content_data="json")
    def new_content(self, gamespace_id, content_name, content_data):

        try:
            yield self.find_content(gamespace_id, content_name)
        except ContentNotFound:
            pass
        else:
            raise ContentError("Content '{0}' already exists.".format(content_name))

        try:
            result = yield self.db.insert("""
                INSERT INTO `contents`
                (`gamespace_id`, `content_name`, `content_json`)
                VALUES (%s, %s, %s);
            """, gamespace_id, content_name, ujson.dumps(content_data))
        except DatabaseError as e:
            raise ContentError("Failed to add new content: " + e.args[1])

        raise Return(result)

    @coroutine
    @validate(gamespace_id="int", content_id="int", content_name="str", content_data="json")
    def update_content(self, gamespace_id, content_id, content_name, content_data):
        try:
            yield self.db.execute("""
                UPDATE `contents`
                SET `content_name`=%s, `content_json`=%s
                WHERE `content_id`=%s AND `gamespace_id`=%s;
            """, content_name, ujson.dumps(content_data), content_id, gamespace_id)
        except DatabaseError as e:
            raise ContentError("Failed to update content: " + e.args[1])


class ContentNotFound(Exception):
    pass

