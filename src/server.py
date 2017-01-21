
from common.options import options

import handler
import common.server
import common.database
import common.access
import common.sign
import common.keyvalue

from common.social.steam import SteamAPI

import admin
import options as _opts

from model.content import ContentModel
from model.store import StoreModel
from model.item import ItemModel
from model.category import CategoryModel
from model.tier import TierModel, CurrencyModel
from model.order import OrdersModel


class StoreServer(common.server.Server):
    # noinspection PyShadowingNames
    def __init__(self):
        super(StoreServer, self).__init__()

        self.db = common.database.Database(
            host=options.db_host,
            database=options.db_name,
            user=options.db_username,
            password=options.db_password)

        self.cache = common.keyvalue.KeyValueStorage(
            host=options.cache_host,
            port=options.cache_port,
            db=options.cache_db,
            max_connections=options.cache_max_connections)

        self.steam_api = SteamAPI(self.cache)

        self.contents = ContentModel(self.db)
        self.items = ItemModel(self.db)
        self.categories = CategoryModel(self.db)
        self.tiers = TierModel(self.db)
        self.currencies = CurrencyModel(self.db)
        self.stores = StoreModel(self.db, self.items, self.tiers, self.currencies)
        self.orders = OrdersModel(self, self.db, self.tiers)

        admin.init()

    def get_models(self):
        return [self.currencies, self.categories, self.stores, self.items, self.contents, self.tiers]

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
            "tiers": admin.StoreTiersController,
            "new_tier_component": admin.NewTierComponentController,
            "tier": admin.StoreTierController,
            "new_tier": admin.NewStoreTierController,
            "currencies": admin.CurrenciesController,
            "currency": admin.CurrencyController,
            "new_currency": admin.NewCurrencyController,
            "orders": admin.OrdersController
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
            (r"/order/new", handler.NewOrderHandler),
            (r"/order/(.*)", handler.OrderHandler),
        ]

if __name__ == "__main__":
    stt = common.server.init()
    common.access.AccessToken.init([common.access.public()])
    common.server.start(StoreServer)
