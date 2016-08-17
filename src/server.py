
from common.options import options

import handler
import common.server
import common.database
import common.access
import common.sign
import common.keyvalue

import admin
import options as _opts

from model.content import ContentModel
from model.store import StoreModel
from model.item import ItemModel
from model.category import CategoryModel
from model.pack import PackModel, CurrencyModel


class StoreServer(common.server.Server):
    # noinspection PyShadowingNames
    def __init__(self):
        super(StoreServer, self).__init__()

        self.db = common.database.Database(
            host=options.db_host,
            database=options.db_name,
            user=options.db_username,
            password=options.db_password)

        self.contents = ContentModel(self.db)
        self.items = ItemModel(self.db)
        self.categories = CategoryModel(self.db)
        self.packs = PackModel(self.db)
        self.currencies = CurrencyModel(self.db)
        self.stores = StoreModel(self.db, self.items, self.packs, self.currencies)

    def get_models(self):
        return [self.categories, self.items, self.contents, self.currencies, self.packs, self.stores]

    def get_admin(self):
        return {
            "index": admin.RootAdminController,
            "contents": admin.ContentsController,
            "content": admin.ContentController,
            "new_content": admin.NewContentController,
            "stores": admin.StoresController,
            "store": admin.StoreController,
            "store_settings": admin.StoreSettingsController,
            "new_store_component": admin.NewStoreComponentController,
            "new_store": admin.NewStoreController,
            "categories": admin.CategoriesController,
            "category": admin.CategoryController,
            "new_category": admin.NewCategoryController,
            "category_common": admin.CategoryCommonController,
            "choose_category": admin.ChooseCategoryController,
            "new_item": admin.NewStoreItemController,
            "item": admin.StoreItemController,
            "packs": admin.StorePacksController,
            "new_pack_component": admin.NewPackComponentController,
            "pack": admin.StorePackController,
            "new_pack": admin.NewStorePackController,
            "currencies": admin.CurrenciesController,
            "currency": admin.CurrencyController,
            "new_currency": admin.NewCurrencyController
        }

    def get_metadata(self):
        return {
            "title": "Store",
            "description": "In-App Purchasing, with server validation",
            "icon": "shopping-cart"
        }

    def get_handlers(self):
        return [
            (r"/store/(.*)", handler.StoreHandler),
        ]

if __name__ == "__main__":
    stt = common.server.init()
    common.access.AccessToken.init([common.access.public()])
    common.server.start(StoreServer)
