
import ujson

from tornado.gen import coroutine, Return
from tornado.web import HTTPError

from common.access import scoped, AccessToken
from common.handler import AuthenticatedHandler

from model.store import StoreNotFound


class StoreHandler(AuthenticatedHandler):
    @scoped()
    @coroutine
    def get(self, store_name):

        stores = self.application.stores

        gamespace = self.token.get(AccessToken.GAMESPACE)

        try:
            store_data = yield stores.find_store_data(
                gamespace,
                store_name)

        except StoreNotFound:
            raise HTTPError(404, "Store not found")

        self.write(ujson.dumps(store_data, ensure_ascii=False))
