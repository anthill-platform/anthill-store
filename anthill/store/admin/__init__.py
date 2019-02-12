from anthill.common.validate import validate

from anthill.common import update as common_update, to_int
import anthill.common.admin as a

from .. model.store import StoreError, StoreNotFound, StoreComponentNotFound
from .. model.category import CategoryError, CategoryNotFound, CategoryModel
from .. model.item import ItemError, ItemNotFound
from .. model.tier import TierModel, TierError, TierNotFound, CurrencyError, CurrencyNotFound
from .. model.order import OrderQueryError, OrdersModel
from ..model.campaign import CampaignError, CampaignNotFound, CampaignItemNotFound

import math
import datetime


class StoreAdminComponents(object):
    COMPONENTS = {}

    @staticmethod
    def component(component_name, action, store_id):
        return StoreAdminComponents.COMPONENTS[component_name](component_name, action, store_id)

    @staticmethod
    def components():
        return list(StoreAdminComponents.COMPONENTS.keys())

    @staticmethod
    def has_component(component_name):
        return component_name in StoreAdminComponents.COMPONENTS

    @staticmethod
    def register_component(component_name, component):
        StoreAdminComponents.COMPONENTS[component_name] = component


class TierAdminComponents(object):
    COMPONENTS = {}

    @staticmethod
    def component(component_name, action, tier_id):
        return TierAdminComponents.COMPONENTS[component_name](component_name, action, tier_id)

    @staticmethod
    def components():
        return list(TierAdminComponents.COMPONENTS.keys())

    @staticmethod
    def has_component(component_name):
        return component_name in TierAdminComponents.COMPONENTS

    @staticmethod
    def register_component(component_name, component):
        TierAdminComponents.COMPONENTS[component_name] = component


class TierComponentAdmin(object):
    def __init__(self, name, action, tier_id, tier_component_class):
        self.action = action
        self.name = name
        self.tier_id = tier_id
        self.component = tier_component_class()

    def dump(self):
        return self.component.dump()

    def get(self):
        return {
            "product": self.component.product
        }

    async def init(self):
        pass

    def load(self, data):
        self.component.load(data)

    # noinspection PyMethodMayBeStatic
    def render(self):
        return {
            "product": a.field("Product ID", "text", "primary", "non-empty")
        }

    def update(self, product, **fields):
        self.component.product = product


# noinspection PyMethodMayBeStatic
class StoreComponentAdmin(object):
    def __init__(self, name, action, store_id, store_component_class):
        self.action = action
        self.name = name
        self.store_id = store_id
        self.component = store_component_class()

    def dump(self):
        return self.component.dump()

    def get(self):
        return {
            "bundle": self.component.bundle
        }

    def get_hook_url(self, app, gamespace_id, store_name, component_name):
        return app.get_host() + "/hook/" + gamespace_id + "/" + store_name + "/" + component_name

    async def init(self):
        pass

    def icon(self):
        return "briefcase"

    def load(self, data):
        self.component.load(data)

    def render(self):
        return {
            "bundle": a.field("Bundle ID", "text", "primary", "non-empty")
        }

    def update(self, bundle, **fields):
        self.component.bundle = bundle


class CategoriesController(a.AdminController):
    async def get(self):
        categories = self.application.categories
        items = await categories.list_categories(self.gamespace)

        result = {
            "items": items
        }

        return result

    def render(self, data):
        return [
            a.breadcrumbs([], "Categories"),
            a.links("Categories", [
                a.link("category", item.name, icon="list-alt", category_id=item.category_id)
                for item in data["items"]
            ]),
            a.links("Navigate", [
                a.link("index", "Go back", icon="chevron-left"),
                a.link("new_category", "Create category", icon="plus"),
                a.link("category_common", "Edit common scheme", icon="bars")
            ])
        ]

    def access_scopes(self):
        return ["store_admin"]


class CategoryCommonController(a.AdminController):
    async def get(self):

        categories = self.application.categories

        try:
            common_scheme = await categories.get_common_scheme(self.gamespace)
            public_item_scheme = common_scheme.public_item_scheme or CategoryModel.DEFAULT_PUBLIC_SCHEME
            private_item_scheme = common_scheme.private_item_scheme or CategoryModel.DEFAULT_PRIVATE_SCHEME
        except CategoryNotFound:
            public_item_scheme = CategoryModel.DEFAULT_PUBLIC_SCHEME
            private_item_scheme = CategoryModel.DEFAULT_PRIVATE_SCHEME

        result = {
            "public_item_scheme": public_item_scheme,
            "private_item_scheme": private_item_scheme
        }

        return result

    def render(self, data):
        return [
            a.breadcrumbs([
                a.link("categories", "Categories")
            ], "Common scheme"),
            a.form("Common scheme shared across categories", fields={
                "public_item_scheme": a.field("Public Item Scheme", "json", "primary", "non-empty", order=1),
                "private_item_scheme": a.field("Private Item Scheme", "json", "primary", "non-empty", order=2),
            }, methods={
                "update": a.method("Update", "primary")
            }, data=data),
            a.links("Navigate", [
                a.link("categories", "Go back", icon="chevron-left"),
                a.link("https://spacetelescope.github.io/understanding-json-schema/index.html", "See docs", icon="book")
            ])
        ]

    def access_scopes(self):
        return ["store_admin"]

    @validate(public_item_scheme="load_json_dict", private_item_scheme="load_json_dict")
    async def update(self, public_item_scheme, private_item_scheme):

        categories = self.application.categories

        try:
            await categories.update_common_scheme(self.gamespace, public_item_scheme, private_item_scheme)
        except CategoryError as e:
            raise a.ActionError("Failed to update common scheme: " + e.args[0])

        raise a.Redirect("category_common", message="Common scheme has been updated")


class CategoryController(a.AdminController):
    async def delete(self, **ignored):

        category_id = self.context.get("category_id")
        categories = self.application.categories

        try:
            await categories.delete_category(self.gamespace, category_id)
        except CategoryError as e:
            raise a.ActionError("Failed to delete category: " + e.args[0])

        raise a.Redirect(
            "categories",
            message="Category has been deleted")

    @validate(category_id="int")
    async def get(self, category_id):

        categories = self.application.categories

        try:
            category = await categories.get_category(self.gamespace, category_id)
        except CategoryNotFound:
            raise a.ActionError("No such category")

        result = {
            "category_name": category.name,
            "category_public_item_scheme": category.public_item_scheme,
            "category_private_item_scheme": category.private_item_scheme
        }

        return result

    def render(self, data):
        return [
            a.breadcrumbs([
                a.link("categories", "Categories")
            ], "Category"),
            a.form("Update category", fields={
                "category_name": a.field("Category unique ID", "text", "primary", "non-empty", order=1),
                "category_public_item_scheme": a.field("Public part of the item, available to everyone",
                                                       "json", "primary", "non-empty", order=2),
                "category_private_item_scheme": a.field("Private part of the item, available only after the purchase",
                                                        "json", "primary", "non-empty", order=3),
            }, methods={
                "update": a.method("Update", "primary"),
                "delete": a.method("Delete this category", "danger")
            }, data=data),
            a.links("Navigate", [
                a.link("categories", "Go back", icon="chevron-left"),
                a.link("category_common", "Edit common scheme", icon="bars"),
                a.link("https://spacetelescope.github.io/understanding-json-schema/index.html", "See docs", icon="book")
            ])
        ]

    def access_scopes(self):
        return ["store_admin"]

    @validate(category_name="str_name", category_public_item_scheme="load_json_dict",
              category_private_item_scheme="load_json_dict")
    async def update(self, category_name, category_public_item_scheme, category_private_item_scheme):

        category_id = self.context.get("category_id")
        categories = self.application.categories

        try:
            await categories.update_category(self.gamespace, category_id, category_name,
                                             category_public_item_scheme, category_private_item_scheme)
        except CategoryError as e:
            raise a.ActionError("Failed to update category: " + e.args[0])

        raise a.Redirect(
            "category",
            message="Category has been updated",
            category_id=category_id)


class ChooseCategoryController(a.AdminController):
    @validate(category="int")
    async def apply(self, category):
        raise a.Redirect(
            "new_item",
            store_id=self.context.get("store_id"),
            category_id=category)

    @validate(store_id="int")
    async def get(self, store_id):
        categories = await self.application.categories.list_categories(self.gamespace)

        try:
            store = await self.application.stores.get_store(self.gamespace, store_id)
        except StoreNotFound:
            raise a.ActionError("No such store")

        return {
            "store_name": store.name,
            "categories": {
                category.category_id: category.name for category in categories
            }
        }

    def render(self, data):
        return [
            a.breadcrumbs([
                a.link("stores", "Stores"),
                a.link("store", data["store_name"], store_id=self.context.get("store_id")),
            ], "Choose category"),
            a.form(
                title="Choose category",
                fields={
                    "category": a.field(
                        "Select category", "select", "primary", values=data["categories"]
                    )
                }, methods={
                    "apply": a.method("Proceed", "primary")
                }, data=data
            ),
            a.links("Navigation", links=[
                a.link("stores", "Go back", icon="chevron-left"),
                a.link("categories", "Manage categories", "list-alt")
            ])
        ]

    def access_scopes(self):
        return ["store_admin"]


class CurrenciesController(a.AdminController):
    async def get(self):
        currencies = self.application.currencies
        items = await currencies.list_currencies(self.gamespace)

        result = {
            "items": items
        }

        return result

    def render(self, data):
        return [
            a.breadcrumbs([], "Currencies"),
            a.links("Items", [
                a.link("currency", item.title + u"({0})".format(item.symbol),
                       icon="bitcoin", currency_id=item.currency_id)
                for item in data["items"]
            ]),
            a.links("Navigate", [
                a.link("index", "Go back", icon="chevron-left"),
                a.link("new_currency", "Create currency", icon="plus")
            ])
        ]

    def access_scopes(self):
        return ["store_admin"]


class CurrencyController(a.AdminController):
    async def delete(self, **ignored):

        currency_id = self.context.get("currency_id")
        currencies = self.application.currencies

        try:
            await currencies.delete_currency(self.gamespace, currency_id)
        except CurrencyError as e:
            raise a.ActionError("Failed to delete currency: " + e.args[0])

        raise a.Redirect("currencies", message="Currency has been deleted")

    @validate(currency_id="int")
    async def get(self, currency_id):

        currencies = self.application.currencies

        try:
            currency = await currencies.get_currency(self.gamespace, currency_id)
        except CurrencyNotFound:
            raise a.ActionError("No such currency")

        result = {
            "currency_name": currency.name,
            "currency_title": currency.title,
            "currency_format": currency.format,
            "currency_symbol": currency.symbol,
            "currency_label": currency.label
        }

        return result

    def render(self, data):
        return [
            a.breadcrumbs([
                a.link("currencies", "Currencies")
            ], data["currency_title"]),
            a.form("Update currency", fields={
                "currency_name": a.field("Currency unique ID", "text", "primary", "non-empty"),
                "currency_title": a.field("Currency title", "text", "primary", "non-empty"),
                "currency_format": a.field(u"Currency format (like ${0} or {0}$)", "text", "primary", "non-empty"),
                "currency_symbol": a.field(u"Currency symbol (like $ or ₴)", "text", "primary", "non-empty"),
                "currency_label": a.field("Currency label (usd, uah)", "text", "primary", "non-empty")
            }, methods={
                "update": a.method("Update", "primary"),
                "delete": a.method("Delete this currency", "danger")
            }, data=data),
            a.links("Navigate", [
                a.link("currencies", "Go back", icon="chevron-left")
            ])
        ]

    def access_scopes(self):
        return ["store_admin"]

    @validate(currency_name="str_name", currency_title="str", currency_format="str",
              currency_symbol="str", currency_label="str")
    async def update(self, currency_name, currency_title, currency_format, currency_symbol, currency_label):

        currency_id = self.context.get("currency_id")

        currencies = self.application.currencies

        try:
            await currencies.update_currency(self.gamespace, currency_id, currency_name, currency_title,
                                             currency_format, currency_symbol, currency_label)
        except CurrencyError as e:
            raise a.ActionError("Failed to update currency: " + e.args[0])

        raise a.Redirect(
            "currency",
            message="Currency has been updated",
            currency_id=currency_id)


class NewCategoryController(a.AdminController):
    @validate(category_name="str_name",
              category_public_item_scheme="load_json_dict",
              category_private_item_scheme="load_json_dict")
    async def create(self, category_name, category_public_item_scheme, category_private_item_scheme):
        categories = self.application.categories

        try:
            category_id = await categories.new_category(self.gamespace, category_name,
                                                        category_public_item_scheme,
                                                        category_private_item_scheme)
        except CategoryError as e:
            raise a.ActionError("Failed to create new category: " + e.args[0])

        raise a.Redirect(
            "category",
            message="New category has been created",
            category_id=category_id)

    def render(self, data):
        return [
            a.breadcrumbs([
                a.link("categories", "Categories")
            ], "New category"),
            a.form("New category", fields={
                "category_name": a.field("Category unique ID", "text", "primary", "non-empty", order=1),
                "category_public_item_scheme": a.field("Public part of the item, available to everyone",
                                                       "json", "primary", "non-empty", order=2),
                "category_private_item_scheme": a.field("Private part of the item, available only after the purchase",
                                                        "json", "primary", "non-empty", order=3)
            }, methods={
                "create": a.method("Create", "primary")
            }, data=data),
            a.links("Navigate", [
                a.link("categories", "Go back", icon="chevron-left"),
                a.link("https://spacetelescope.github.io/understanding-json-schema/index.html", "See docs", icon="book")
            ])
        ]

    async def get(self):

        categories = self.application.categories

        try:
            common_scheme = await categories.get_common_scheme(self.gamespace)
            public_item_scheme = common_scheme.public_item_scheme or CategoryModel.DEFAULT_PUBLIC_SCHEME
            private_item_scheme = common_scheme.private_item_scheme or CategoryModel.DEFAULT_PRIVATE_SCHEME
        except CategoryNotFound:
            public_item_scheme = CategoryModel.DEFAULT_PUBLIC_SCHEME
            private_item_scheme = CategoryModel.DEFAULT_PRIVATE_SCHEME

        return {
            "category_public_item_scheme": public_item_scheme,
            "category_private_item_scheme": private_item_scheme
        }

    def access_scopes(self):
        return ["store_admin"]


class NewCurrencyController(a.AdminController):
    @validate(currency_name="str_name", currency_title="str", currency_format="str",
              currency_symbol="str", currency_label="str")
    async def create(self, currency_name, currency_title, currency_format, currency_symbol, currency_label):

        currencies = self.application.currencies

        try:
            currency_id = await currencies.new_currency(self.gamespace, currency_name, currency_title,
                                                        currency_format, currency_symbol, currency_label)
        except CurrencyError as e:
            raise a.ActionError("Failed to create new currency: " + e.args[0])

        raise a.Redirect(
            "currency",
            message="New currency has been created",
            currency_id=currency_id)

    def render(self, data):
        return [
            a.breadcrumbs([
                a.link("currencies", "Currencies")
            ], "New currency"),
            a.form("New currency", fields={
                "currency_name": a.field("Currency unique ID", "text", "primary", "non-empty"),
                "currency_title": a.field("Currency title", "text", "primary", "non-empty"),
                "currency_format": a.field(u"Currency format (like ${0} or {0}$)", "text", "primary", "non-empty"),
                "currency_symbol": a.field(u"Currency symbol (like $ or ₴)", "text", "primary", "non-empty"),
                "currency_label": a.field("Currency label (usd, uah)", "text", "primary", "non-empty")
            }, methods={
                "create": a.method("Create", "primary")
            }, data={"currency_format": "${0}", "currency_symbol": "$"}),
            a.links("Navigate", [
                a.link("currencies", "Go back", icon="chevron-left")
            ])
        ]

    def access_scopes(self):
        return ["store_admin"]


class NewTierComponentController(a.AdminController):
    async def create_component(self, **args):
        tiers = self.application.tiers

        component_name = self.context.get("component")
        tier_id = self.context.get("tier_id")

        if not TierAdminComponents.has_component(component_name):
            raise a.ActionError("Component '{0}' is not supported.")

        component_admin = await self.get_component(component_name, tier_id)
        component_admin.update(**args)
        component_data = component_admin.dump()

        try:
            await tiers.new_tier_component(self.gamespace, tier_id, component_name, component_data)
        except StoreError as e:
            raise a.ActionError("Failed to create store component: " + str(e))

        raise a.Redirect(
            "tier",
            message="Component has been created",
            tier_id=tier_id)

    @validate(tier_id="int")
    async def get(self, tier_id):
        stores = self.application.stores
        tiers = self.application.tiers

        try:
            tier = await tiers.get_tier(self.gamespace, tier_id)
        except StoreNotFound:
            raise a.ActionError("No such tier")

        try:
            store = await stores.get_store(self.gamespace, tier.store_id)
        except StoreNotFound:
            raise a.ActionError("No such store")

        try:
            existent_components = await tiers.list_tier_components(self.gamespace, tier_id)
        except StoreError as e:
            raise a.ActionError("Failed to get tier components: " + str(e))
        else:
            existent_components = set(component.name for component in existent_components)

        new_components = set(TierAdminComponents.components())
        components = list(new_components - existent_components)

        return {
            "components": {component: component for component in components},
            "store_name": store.name,
            "tier_name": tier.name
        }

    async def get_component(self, component, tier_id):
        try:
            component_instance = TierAdminComponents.component(component, self, tier_id)
        except KeyError:
            raise a.ActionError("No such tier component")

        await component_instance.init()

        return component_instance

    def render(self, data):

        tier_id = self.context.get("tier_id")
        store_id = self.context.get("store_id")

        result = [
            a.breadcrumbs([
                a.link("stores", "Stores"),
                a.link("store", data["store_name"], store_id=store_id),
                a.link("tiers", "Tiers", store_id=store_id),
                a.link("tier", data["tier_name"], tier_id=tier_id)
            ], "New tier component")
        ]

        if "component" in data:
            component = data["component"]

            result.extend([
                a.form("New tier component: {0}".format(component.name), fields=component.render(), methods={
                    "create_component": a.method("Create component", "primary")
                }, data=component.get(), icon="briefcase", component=component.name)
            ])
        else:
            components = data["components"]
            if components:
                result.extend([
                    a.form("Add new component", fields={
                        "component": a.field("Type", "select", "primary", values=components)
                    }, methods={
                        "select": a.method("Proceed", "primary")
                    }, data=data, icon="briefcase")
                ])
            else:
                result.extend([
                    a.notice("No components", "No components to create")
                ])

        result.extend([
            a.links("Navigate", [
                a.link("tier", "Go back", icon="chevron-left", tier_id=tier_id),
            ])
        ])

        return result

    def access_scopes(self):
        return ["store_admin"]

    @validate(component="str_name")
    async def select(self, component):
        stores = self.application.stores
        tiers = self.application.tiers

        tier_id = self.context.get("tier_id")

        try:
            tier = await tiers.get_tier(self.gamespace, tier_id)
        except StoreNotFound:
            raise a.ActionError("No such tier")

        try:
            store = await stores.get_store(self.gamespace, tier.store_id)
        except StoreNotFound:
            raise a.ActionError("No such store")

        component = await self.get_component(component, tier_id)

        return {
            "store_name": store.name,
            "tier_name": tier.name,
            "component": component
        }


class NewStoreComponentController(a.AdminController):
    async def create_component(self, **args):
        stores = self.application.stores

        component_name = self.context.get("component")
        store_id = self.context.get("store_id")

        if not StoreAdminComponents.has_component(component_name):
            raise a.ActionError("Component '{0}' is not supported.")

        component_admin = await self.get_component(component_name, store_id)
        component_admin.update(**args)
        component_data = component_admin.dump()

        try:
            await stores.new_store_component(self.gamespace, store_id, component_name, component_data)
        except StoreError as e:
            raise a.ActionError("Failed to create store component: " + str(e))

        raise a.Redirect(
            "store_settings",
            message="New component has been created",
            store_id=store_id)

    @validate(store_id="int")
    async def get(self, store_id):

        stores = self.application.stores

        try:
            store = await stores.get_store(self.gamespace, store_id)
        except StoreNotFound:
            raise a.ActionError("No such store")

        try:
            existent_components = await stores.list_store_components(self.gamespace, store_id)
        except StoreError as e:
            raise a.ActionError("Failed to get store components: " + e.message)
        else:
            existent_components = set(component.name for component in existent_components)

        new_components = set(StoreAdminComponents.components())
        components = list(new_components - existent_components)

        return {
            "components": {component: component for component in components},
            "store_name": store.name
        }

    async def get_component(self, component, store_id):
        try:
            component_instance = StoreAdminComponents.component(component, self, store_id)
        except KeyError:
            raise a.ActionError("No such store component")

        await component_instance.init()

        return component_instance

    def render(self, data):

        store_id = self.context.get("store_id")

        result = [
            a.breadcrumbs([
                a.link("stores", "Stores"),
                a.link("store", data["store_name"], store_id=store_id),
                a.link("store_settings", "Settings", store_id=store_id)
            ], "New component")
        ]

        if "component" in data:
            component = data["component"]

            result.extend([
                a.form("New store component: {0}".format(component.name), fields=component.render(), methods={
                    "create_component": a.method("Create component", "primary")
                }, data=component.get(), icon=component.icon(), component=component.name)
            ])
        else:
            components = data["components"]
            if components:
                result.extend([
                    a.form("Add new component", fields={
                        "component": a.field("Type", "select", "primary", values=components)
                    }, methods={
                        "select": a.method("Proceed", "primary")
                    }, data=data, icon="briefcase")
                ])
            else:
                result.extend([
                    a.notice("No components", "No components to create")
                ])

        result.extend([
            a.links("Navigate", [
                a.link("store_settings", "Go back", icon="chevron-left", store_id=store_id),
            ])
        ])

        return result

    def access_scopes(self):
        return ["store_admin"]

    @validate(component="str_name")
    async def select(self, component):

        stores = self.application.stores
        store_id = self.context.get("store_id")

        try:
            store = await stores.get_store(self.gamespace, store_id)
        except StoreNotFound:
            raise a.ActionError("No such store")

        component = await self.get_component(component, store_id)

        return {
            "store_name": store.name,
            "component": component
        }


class NewStoreController(a.AdminController):
    @validate(store_name="str_name")
    async def create(self, store_name):
        stores = self.application.stores

        try:
            store_id = await stores.new_store(self.gamespace, store_name, {})
        except StoreError as e:
            raise a.ActionError("Failed to create new store: " + e.args[0])

        raise a.Redirect(
            "store",
            message="New store has been created",
            store_id=store_id)

    def render(self, data):
        return [
            a.breadcrumbs([
                a.link("stores", "Stores")
            ], "New store"),
            a.form("New store", fields={
                "store_name": a.field("Store unique ID", "text", "primary", "non-empty", order=1)
            }, methods={
                "create": a.method("Create", "primary")
            }, data=data),
            a.links("Navigate", [
                a.link("stores", "Go back", icon="chevron-left")
            ])
        ]

    def access_scopes(self):
        return ["store_admin"]


class NewStoreItemController(a.AdminController):
    @validate(item_name="str_name", item_enabled="bool", tier_id="int",
              item_public_data="load_json", item_private_data="load_json")
    async def create(self, item_name, item_public_data, item_private_data,
                     item_tier, item_enabled=False, **method_data):
        items = self.application.items
        stores = self.application.stores
        tiers = self.application.tiers

        store_id = self.context.get("store_id")
        category_id = self.context.get("category_id")

        try:
            await stores.get_store(self.gamespace, store_id)
        except StoreNotFound:
            raise a.ActionError("No such store")

        try:
            tier = await tiers.get_tier(self.gamespace, item_tier)
        except TierNotFound:
            raise a.ActionError("No such tier")
        else:
            if str(tier.store_id) != str(store_id):
                raise a.ActionError("Bad tier")

        try:
            item_id = await items.new_item(
                self.gamespace, store_id, category_id, item_name,
                item_enabled, item_public_data, item_private_data, item_tier)
        except ItemError as e:
            raise a.ActionError(e.message)

        raise a.Redirect(
            "item",
            message="New item has been created",
            item_id=item_id)

    @validate(store_id="int", category_id="int", clone="int")
    async def get(self, store_id, category_id, clone=None):

        stores = self.application.stores
        categories = self.application.categories
        items = self.application.items
        tiers = self.application.tiers

        try:
            await stores.get_store(self.gamespace, store_id)
        except StoreNotFound:
            raise a.ActionError("No such store")

        tiers_list = await tiers.list_tiers(self.gamespace, store_id)

        if clone:
            try:
                item = await items.get_item(self.gamespace, clone)
            except ItemNotFound:
                raise a.ActionError("No item to clone from")
            except ItemError as e:
                raise a.ActionError("Failed to clone item: " + e.message)

            item_name = item.name
            item_public_data = item.public_data
            item_private_data = item.private_data
            item_tier = item.tier
            item_enabled = item.enabled
        else:
            item_name = ""
            item_public_data = {}
            item_private_data = {}
            item_tier = 0
            item_enabled = True

        try:
            store = await stores.get_store(self.gamespace, store_id)
        except StoreNotFound:
            raise a.ActionError("No such store")

        try:
            category = await categories.get_category(self.gamespace, category_id)
        except CategoryNotFound:
            raise a.ActionError("No such category")

        try:
            common_scheme = await categories.get_common_scheme(self.gamespace)
        except CategoryNotFound:
            common_public_item_scheme = {}
            common_private_item_scheme = {}
        else:
            common_public_item_scheme = common_scheme.public_item_scheme
            common_private_item_scheme = common_scheme.private_item_scheme

        public_item_scheme = category.public_item_scheme
        private_item_scheme = category.private_item_scheme

        common_update(public_item_scheme, common_public_item_scheme)
        common_update(private_item_scheme, common_private_item_scheme)

        data = {
            "category_name": category.name,
            "store_name": store.name,
            "public_item_scheme": public_item_scheme,
            "private_item_scheme": private_item_scheme,
            "item_tier": item_tier,
            "tiers_list": {tier.tier_id: u"{0} ({1})".format(tier.title, tier.name) for tier in tiers_list},
            "item_name": item_name,
            "item_public_data": item_public_data,
            "item_private_data": item_private_data,
            "item_enabled": "true" if item_enabled else "false"
        }

        return data

    def render(self, data):
        return [
            a.breadcrumbs([
                a.link("stores", "Stores"),
                a.link("store", data["store_name"], store_id=self.context.get("store_id"))
            ], "Add new item to store"),
            a.form("New item (of category '{0}')".format(data["category_name"]), fields={
                "item_name": a.field(
                    "Item Unique Name", "text", "primary", "non-empty",
                    order=1, description="Item unique name per store for internal purposes"),
                "item_tier": a.field(
                    "Item Price Tier", "select", "primary",
                    values=data["tiers_list"], order=2),
                "item_enabled": a.field(
                    "Is Item Enabled?", "switch", "primary",
                    order=3, description="Only enabled items will be sent to the users"),
                "item_public_data": a.field(
                    "Public Item Properties", "dorn", "primary",
                    schema=data["public_item_scheme"], order=4, description="Available to everyone"),
                "item_private_data": a.field(
                    "Private Item Properties", "dorn", "primary",
                    schema=data["private_item_scheme"], order=5,
                    description="Available only as a response to successful purchase")
            }, methods={
                "create": a.method("Clone" if self.context.get("clone") else "Create", "primary")
            }, data=data),
            a.links("Navigate", [
                a.link("store", "Go back", icon="chevron-left", store_id=self.context.get("store_id")),
                a.link("category", "Edit category scheme", icon="list-alt", category_id=self.context.get("category_id"))
            ])
        ]

    def access_scopes(self):
        return ["store_admin"]


class NewStoreTierController(a.AdminController):
    @validate(tier_name="str_name", tier_title="str", tier_product="str", tier_prices="load_json_dict_of_ints")
    async def create(self, tier_name, tier_title, tier_product, tier_prices):

        tiers = self.application.tiers
        store_id = self.context.get("store_id")

        try:
            tier_id = await tiers.new_tier(self.gamespace, store_id, tier_name, tier_title, tier_product, tier_prices)
        except StoreError as e:
            raise a.ActionError("Failed to create new tier: " + e.args[0])

        raise a.Redirect(
            "tier",
            message="New tier has been created",
            tier_id=tier_id)

    @validate(store_id="int")
    async def get(self, store_id):

        stores = self.application.stores
        currencies = self.application.currencies

        try:
            store = await stores.get_store(self.gamespace, store_id)
        except StoreNotFound:
            raise a.ActionError("No such store")

        return {
            "store_name": store.name,
            "currencies": (await currencies.list_currencies(self.gamespace)),
            "tier_prices": {}
        }

    def render(self, data):
        return [
            a.breadcrumbs([
                a.link("stores", "Stores"),
                a.link("store", data["store_name"], store_id=self.context.get("store_id")),
                a.link("tiers", "Tiers", store_id=self.context.get("store_id"))
            ], "Add new tier to store"),
            a.form("New tier", fields={
                "tier_name": a.field(
                    "Tier unique name", "text", "primary", "non-empty",
                    order=1, description="Unique name per store, for internal purposes"),
                "tier_title": a.field(
                    "Tier title", "text", "primary", "non-empty",
                    order=2, description="A short description for usage ease, for example, \"$0.99\""),
                "tier_product": a.field(
                    "Product ID", "text", "primary", "non-empty",
                    order=3),
                "tier_prices": a.field(
                    "Tier prices (in cents)", "kv", "primary",
                    values={curr.name: curr.title for curr in data["currencies"]},
                    order=4
                )
            }, methods={
                "create": a.method("Create", "primary")
            }, data=data),
            a.links("Navigate", [
                a.link("contents", "Go back", icon="chevron-left"),
                a.link("currencies", "Edit currencies", icon="bitcoin")
            ])
        ]

    def access_scopes(self):
        return ["store_admin"]


class RootAdminController(a.AdminController):
    def render(self, data):
        return [
            a.links("Store service", [
                a.link("stores", "Edit stores", icon="shopping-bag"),
                a.link("categories", "Edit categories", icon="list-alt"),
                a.link("currencies", "Edit currencies", icon="bitcoin"),
            ])
        ]

    def access_scopes(self):
        return ["store_admin"]


class StoreController(a.AdminController):
    @validate(store_id="int")
    async def get(self, store_id):

        stores = self.application.stores
        items = self.application.items

        try:
            store = await stores.get_store(self.gamespace, store_id)
        except StoreNotFound:
            raise a.ActionError("No such store")

        items = await items.list_items(self.gamespace, store_id)

        result = {
            "items": items,
            "store_name": store.name
        }

        return result

    def render(self, data):
        return [
            a.breadcrumbs([
                a.link("stores", "Stores")
            ], data["store_name"]),
            a.content("Items", [
                {
                    "id": "name",
                    "title": "Name"
                },
                {
                    "id": "enabled",
                    "title": "Enabled"
                },
                {
                    "id": "title",
                    "title": "Title"
                },
                {
                    "id": "category",
                    "title": "Category"
                },
                {
                    "id": "tier",
                    "title": "Tier"
                },
                {
                    "id": "actions",
                    "title": "Actions"
                }
            ], [
                          {
                              "name": [
                                  a.link("item", entry.item.name, icon="shopping-bag", item_id=entry.item.item_id)],
                              "category": [
                                  a.link(
                                      "category", entry.category.name,
                                      icon="list-alt", category_id=entry.category.category_id)
                              ],
                              "tier": [a.link("tier", entry.tier.title, tier_id=entry.tier.tier_id)],
                              "title": entry.item.title("EN"),
                              "enabled": [
                                  a.status("Yes" if entry.item.enabled else "No",
                                           "success" if entry.item.enabled else "danger")
                              ],
                              "actions": [
                                  a.button("item", "Delete", "danger", _method="delete", item_id=entry.item.item_id)]
                          }
                          for entry in data["items"]
                      ], "default"),

            a.links("Navigate", [
                a.link("stores", "Go back", icon="chevron-left"),
                a.link("tiers", "Edit tiers", icon="diamond", store_id=self.context.get("store_id")),
                a.link("orders", "Orders", icon="money", store_id=self.context.get("store_id")),
                a.link("campaigns", "Campaigns", icon="percent", store_id=self.context.get("store_id")),
                a.link("store_settings", "Store settings", icon="cog", store_id=self.context.get("store_id")),
                a.link("choose_category", "Add new item", icon="plus", store_id=self.context.get("store_id")),
            ])
        ]

    def access_scopes(self):
        return ["store_admin"]


class StoreItemController(a.AdminController):
    async def delete(self, **ignored):
        items = self.application.items

        item_id = self.context.get("item_id")

        try:
            item = await items.get_item(self.gamespace, item_id)
        except ItemNotFound:
            raise a.ActionError("No such item")

        store_id = item.store_id

        try:
            await items.delete_item(self.gamespace, item_id)
        except ItemError as e:
            raise a.ActionError("Failed to delete item: " + e.message)

        raise a.Redirect(
            "store",
            message="Item has been deleted",
            store_id=store_id)

    @validate(item_id="int")
    async def get(self, item_id):

        stores = self.application.stores
        items = self.application.items
        categories = self.application.categories
        tiers = self.application.tiers

        try:
            item = await items.get_item(self.gamespace, item_id)
        except ItemNotFound:
            raise a.ActionError("No such item")

        store_id = item.store_id
        category_id = item.category

        try:
            store = await stores.get_store(self.gamespace, store_id)
        except StoreNotFound:
            raise a.ActionError("No such store")

        tiers_list = await tiers.list_tiers(self.gamespace, store_id)

        try:
            category = await categories.get_category(self.gamespace, category_id)
        except CategoryNotFound:
            raise a.ActionError("No such category")

        try:
            common_scheme = await categories.get_common_scheme(self.gamespace)
        except CategoryNotFound:
            common_public_item_scheme = {}
            common_private_item_scheme = {}
        else:
            common_public_item_scheme = common_scheme.public_item_scheme
            common_private_item_scheme = common_scheme.private_item_scheme

        public_item_scheme = category.public_item_scheme
        private_item_scheme = category.private_item_scheme

        common_update(public_item_scheme, common_public_item_scheme)
        common_update(private_item_scheme, common_private_item_scheme)

        return {
            "category_name": category.name,
            "category_id": category_id,
            "store_name": store.name,
            "public_item_scheme": public_item_scheme,
            "private_item_scheme": private_item_scheme,
            "item_name": item.name,
            "item_enabled": "true" if item.enabled else "false",
            "item_public_data": item.public_data,
            "item_private_data": item.private_data,
            "tiers_list": {tier.tier_id: u"{0} ({1})".format(tier.title, tier.name) for tier in tiers_list},
            "item_tier": item.tier,
            "store_id": store_id
        }

    def render(self, data):

        return [
            a.breadcrumbs([
                a.link("stores", "Stores"),
                a.link("store", data["store_name"], store_id=data.get("store_id"))
            ], data["item_name"]),
            a.form("Store item (of category '{0}')".format(data["category_name"]), fields={
                "item_name": a.field(
                    "Item Unique Name", "text", "primary", "non-empty",
                    order=1, description="Item unique name per store for internal purposes"),
                "item_tier": a.field(
                    "Item Price Tier", "select", "primary",
                    values=data["tiers_list"], order=2),
                "item_enabled": a.field(
                    "Is Item Enabled?", "switch", "primary",
                    order=3, description="Only enabled items will be sent to the users"),
                "item_public_data": a.field(
                    "Public Item Properties", "dorn", "primary",
                    schema=data["public_item_scheme"], order=4, description="Available to everyone"),
                "item_private_data": a.field(
                    "Private Item Properties", "dorn", "primary",
                    schema=data["private_item_scheme"], order=5,
                    description="Available only as a response to successful purchase")
            }, methods={
                "update": a.method("Update", "primary"),
                "delete": a.method("Delete this item", "danger"),
            }, data=data),
            a.links("Navigate", [
                a.link("store", "Go back", icon="chevron-left", store_id=data.get("store_id")),
                a.link("new_item", "Clone this item",
                       icon="clone",
                       store_id=data.get("store_id"),
                       clone=self.context.get("item_id"),
                       category_id=data.get("category_id")),
                a.link("category", "Edit category scheme", icon="list-alt", category_id=data.get("category_id"))
            ])
        ]

    # noinspection PyUnusedLocal
    def access_scopes(self):
        return ["store_admin"]

    @validate(item_name="str_name", item_enabled="bool", item_public_data="load_json",
              item_private_data="load_json", item_tier="int")
    async def update(self, item_name, item_public_data, item_private_data, item_tier, item_enabled=False, **ignored):
        items = self.application.items
        tiers = self.application.tiers

        item_id = self.context.get("item_id")

        try:
            item = await items.get_item(self.gamespace, item_id)
        except ItemNotFound:
            raise a.ActionError("No such item")

        try:
            tier = await tiers.get_tier(self.gamespace, item_tier)
        except TierNotFound:
            raise a.ActionError("No such tier")
        else:
            if str(tier.store_id) != str(item.store_id):
                raise a.ActionError("Bad tier")

        try:
            await items.update_item(self.gamespace, item_id,
                                    item_name, item_enabled, item_public_data,
                                    item_private_data, item_tier)
        except ItemError as e:
            raise a.ActionError("Failed to update item: " + e.args[0])

        raise a.Redirect(
            "item",
            message="Item has been updated",
            item_id=item_id)


class StoreTierController(a.AdminController):
    async def change_component(self, **args):
        tiers = self.application.tiers

        component_id = self.context.get("component_id")
        tier_id = self.context.get("tier_id")

        try:
            component = await tiers.get_tier_component(self.gamespace, tier_id, component_id)
        except StoreComponentNotFound as e:
            raise a.ActionError("No such tier component")

        name = component.name

        if not TierAdminComponents.has_component(name):
            raise a.ActionError("Component '{0}' is not supported.")

        component_admin = await self.get_component(name, tier_id)
        component_admin.update(**args)
        component_data = component_admin.dump()

        try:
            await tiers.update_tier_component(self.gamespace, tier_id, component_id, component_data)
        except StoreError as e:
            raise a.ActionError("Failed to update tier component: " + str(e))

        raise a.Redirect(
            "tier",
            message="Component has been updated",
            tier_id=tier_id)

    async def delete(self, **ignore):

        tiers = self.application.tiers
        tier_id = self.context.get("tier_id")

        try:
            tier = await tiers.get_tier(self.gamespace, tier_id)
        except TierNotFound:
            raise a.ActionError("Tier not found")

        store_id = tier.store_id

        try:
            await tiers.delete_tier(self.gamespace, tier_id)
        except StoreError as e:
            raise a.ActionError("Failed to delete tier: " + e.args[0])

        raise a.Redirect(
            "tiers",
            message="Tier has been deleted",
            store_id=store_id)

    async def delete_component(self, **args):
        tiers = self.application.tiers

        component_id = self.context.get("component_id")
        tier_id = self.context.get("tier_id")

        try:
            await tiers.delete_tier_component(self.gamespace, tier_id, component_id)
        except StoreError as e:
            raise a.ActionError("Failed to delete tier component: " + str(e))

        raise a.Redirect(
            "tier",
            message="Component has been deleted",
            tier_id=tier_id)

    @validate(tier_id="int")
    async def get(self, tier_id):

        stores = self.application.stores
        currencies = self.application.currencies
        tiers = self.application.tiers

        try:
            tier = await tiers.get_tier(self.gamespace, tier_id)
        except TierNotFound:
            raise a.ActionError("Tier not found")

        store_id = tier.store_id

        try:
            store = await stores.get_store(self.gamespace, store_id)
        except StoreNotFound:
            raise a.ActionError("No such store")

        try:
            tier_components = await tiers.list_tier_components(self.gamespace, tier_id)
        except StoreError as e:
            raise a.ActionError("Failed to get store components: " + str(e))

        components = {}

        for component in tier_components:
            if StoreAdminComponents.has_component(component.name):
                component_admin = await self.get_component(component.name, tier_id)
                component_admin.load(component.data)
                components[component.component_id] = component_admin

        return {
            "store_name": store.name,
            "store_id": store_id,
            "currencies": (await currencies.list_currencies(self.gamespace)),
            "tier_prices": tier.prices,
            "tier_name": tier.name,
            "tier_title": tier.title,
            "tier_product": tier.product,
            "components": components
        }

    async def get_component(self, component, tier_id):
        try:
            component_instance = TierAdminComponents.component(component, self, tier_id)
        except KeyError:
            raise a.ActionError("No such tier component")

        await component_instance.init()

        return component_instance

    def render(self, data):
        result = [
            a.breadcrumbs([
                a.link("stores", "Stores"),
                a.link("store", data["store_name"], store_id=data["store_id"]),
                a.link("tiers", "Tiers", store_id=data["store_id"])
            ], data["tier_name"]),
            a.form("Edit tier", fields={
                "tier_name": a.field(
                    "Tier unique name", "text", "primary", "non-empty",
                    order=1, description="Unique name per store, for internal purposes"),
                "tier_title": a.field(
                    "Tier title", "text", "primary", "non-empty",
                    order=2, description="A short description for usage ease, for example, \"$0.99\""),
                "tier_product": a.field(
                    "Product ID", "text", "primary", "non-empty",
                    order=3),
                "tier_prices": a.field(
                    "Tier prices (in cents)", "kv", "primary",
                    values={curr.name: curr.title for curr in data["currencies"]},
                    order=4
                )
            }, methods={
                "update": a.method("Update tier", "primary"),
                "delete": a.method("Delete tier", "danger")
            }, data=data)
        ]

        for component_id, component in data["components"].items():
            result.append(a.form(component.name, fields=component.render(), methods={
                "change_component": a.method("Update component", "primary"),
                "delete_component": a.method("Delete component", "danger")
            }, data=component.get(), icon="briefcase", component_id=component_id))

        result.extend([
            a.links("Navigate", [
                a.link("store", "Go back", icon="chevron-left", store_id=data["store_id"]),
                a.link("currencies", "Edit currencies", icon="bitcoin"),
                a.link("new_tier_component", "New component", icon="briefcase",
                       tier_id=self.context.get("tier_id"))
            ])
        ])

        return result

    def access_scopes(self):
        return ["store_admin"]

    @validate(tier_name="str_name", tier_title="str", tier_product="str", tier_prices="load_json_dict_of_ints")
    async def update(self, tier_name, tier_title, tier_product, tier_prices):

        tiers = self.application.tiers
        tier_id = self.context.get("tier_id")

        try:
            await tiers.update_tier(self.gamespace, tier_id, tier_name, tier_title, tier_product, tier_prices)
        except StoreError as e:
            raise a.ActionError("Failed to update tier: " + e.args[0])

        raise a.Redirect(
            "tier",
            message="Tier has been updated",
            tier_id=tier_id)


class StoreTiersController(a.AdminController):
    @validate(store_id="int")
    async def get(self, store_id):

        stores = self.application.stores
        tiers = self.application.tiers

        try:
            store = await stores.get_store(self.gamespace, store_id)
        except StoreNotFound:
            raise a.ActionError("No such store")

        tiers = await tiers.list_tiers(self.gamespace, store_id)

        result = {
            "tiers": tiers,
            "store_name": store.name
        }

        return result

    def render(self, data):
        return [
            a.breadcrumbs([
                a.link("stores", "Stores"),
                a.link("store", data["store_name"], store_id=self.context.get("store_id"))
            ], "Tiers"),
            a.content("Items", [
                {
                    "id": "name",
                    "title": "Name"
                },
                {
                    "id": "title",
                    "title": "Title"
                },
                {
                    "id": "product",
                    "title": "Product ID"
                },
                {
                    "id": "actions",
                    "title": "Actions"
                }
            ], [{"name": [a.link("tier", str(tier.name), icon="diamond", tier_id=tier.tier_id)],
                 "product": tier.product,
                 "title": tier.title,
                 "actions": [a.button("tier", "Delete", "danger", _method="delete", tier_id=tier.tier_id)]
                 } for tier in data["tiers"]
                ], "default"),
            a.links("Navigate", [
                a.link("store", "Go back", icon="chevron-left", store_id=self.context.get("store_id")),
                a.link("currencies", "Edit currencies", icon="bitcoin"),
                a.link("new_tier", "Add new tier", icon="plus", store_id=self.context.get("store_id")),
            ])
        ]

    def access_scopes(self):
        return ["store_admin"]


class StoreSettingsController(a.AdminController):
    async def change_component(self, **args):
        stores = self.application.stores

        component_id = self.context.get("component_id")
        store_id = self.context.get("store_id")

        try:
            component = await stores.get_store_component(self.gamespace, store_id, component_id)
        except StoreComponentNotFound:
            raise a.ActionError("No such store component")

        name = component.name

        if not StoreAdminComponents.has_component(name):
            raise a.ActionError("Component '{0}' is not supported.")

        component_admin = await self.get_component(name, store_id)
        component_admin.update(**args)
        component_data = component_admin.dump()

        try:
            await stores.update_store_component(self.gamespace, store_id, component_id, component_data)
        except StoreError as e:
            raise a.ActionError("Failed to update store component: " + str(e))

        raise a.Redirect(
            "store_settings",
            message="Component has been updated",
            store_id=store_id)

    async def delete(self, danger):
        store_id = self.context.get("store_id")
        stores = self.application.stores

        if danger != "confirm":
            raise a.Redirect("store_settings", store_id=store_id)

        try:
            await stores.delete_store(self.gamespace, store_id)
        except StoreError as e:
            raise a.ActionError("Failed to delete store: " + e.args[0])

        raise a.Redirect("stores", message="Store has been deleted")

    async def delete_component(self, **args):
        stores = self.application.stores

        component_id = self.context.get("component_id")
        store_id = self.context.get("store_id")

        try:
            await stores.delete_store_component(self.gamespace, store_id, component_id)
        except StoreError as e:
            raise a.ActionError("Failed to delete store component: " + str(e))

        raise a.Redirect(
            "store_settings",
            message="Component has been deleted",
            store_id=store_id)

    @validate(store_id="int")
    async def get(self, store_id):

        stores = self.application.stores

        try:
            store = await stores.get_store(self.gamespace, store_id)
        except StoreNotFound:
            raise a.ActionError("No such store")

        try:
            store_components = await stores.list_store_components(self.gamespace, store_id)
        except StoreError as e:
            raise a.ActionError("Failed to get store components: " + str(e))

        components = {}

        for component in store_components:
            if StoreAdminComponents.has_component(component.name):
                component_admin = await self.get_component(component.name, store_id)
                component_admin.load(component.data)
                components[component.component_id] = component_admin

        return {
            "store_name": store.name,
            "store_components": components,
            "store_campaign_scheme": store.campaign_scheme or {}
        }

    async def get_component(self, component, store_id):
        try:
            component_instance = StoreAdminComponents.component(component, self, store_id)
        except KeyError:
            raise a.ActionError("No such store component")

        await component_instance.init()

        return component_instance

    def render(self, data):
        store_id = self.context.get("store_id")

        result = [
            a.breadcrumbs([
                a.link("stores", "Stores"),
                a.link("store", data["store_name"], store_id=store_id)
            ], "Settings")
        ]

        for component_id, component in data["store_components"].items():
            component_fields = component.render()
            component_data = component.get()

            if component.component.is_hook_applicable():
                component_fields.update({
                    "hook_url": a.field("Backend hook URL", "readonly", "danger", "non-empty")
                })

                component_data.update({
                    "hook_url": component.get_hook_url(
                        self.application, self.gamespace, data["store_name"], component.name)
                })

            result.append(a.form(component.name, fields=component_fields, methods={
                "change_component": a.method("Update component", "primary"),
                "delete_component": a.method("Delete component", "danger")
            }, data=component_data, icon=component.icon(), component_id=component_id))

        result.extend([
            a.form("Store info", fields={
                "store_name": a.field("Store unique ID", "text", "primary", "non-empty", order=1),
                "store_campaign_scheme": a.field("Store Campaign Scheme", "json", "primary", "non-empty",
                                                 order=2, height=300)
            }, methods={
                "update": a.method("Update", "primary")
            }, data=data),
            a.form("Delete this store", fields={
                "danger": a.field("This cannot be undone! Type 'confirm' to do this.", "text", "danger",
                                  "non-empty")
            }, methods={
                "delete": a.method("Delete this store", "danger")
            }, data=data),
            a.links("Navigate", [
                a.link("store", "Go back", icon="chevron-left", store_id=store_id),
                a.link("new_store_component", "New component", icon="briefcase", store_id=store_id),
            ])
        ])

        return result

    def access_scopes(self):
        return ["store_admin"]

    @validate(store_name="str_name", store_campaign_scheme="load_json_dict")
    async def update(self, store_name, store_campaign_scheme):

        store_id = self.context.get("store_id")
        stores = self.application.stores

        try:
            await stores.update_store(self.gamespace, store_id, store_name, store_campaign_scheme)
        except StoreError as e:
            raise a.ActionError("Failed to update store: " + e.args[0])

        raise a.Redirect(
            "store_settings",
            message="Store settings have been updated",
            store_id=store_id)


class StoresController(a.AdminController):
    async def get(self):
        stores = await self.application.stores.list_stores(self.gamespace)

        result = {
            "stores": stores
        }

        return result

    def render(self, data):
        return [
            a.breadcrumbs([], "Stores"),
            a.links("Stores", [
                a.link("store", item.name, icon="shopping-bag", store_id=item.store_id)
                for item in data["stores"]
            ]),
            a.links("Navigate", [
                a.link("index", "Go back", icon="chevron-left"),
                a.link("new_store", "Create a new store", icon="plus")
            ])
        ]

    def access_scopes(self):
        return ["store_admin"]


class OrdersController(a.AdminController):
    ORDERS_PER_PAGE = 20

    def render(self, data):
        orders = [
            {
                "tier": [
                    a.link("tier", order.tier.name, icon="diamond", tier_id=order.tier.tier_id)
                ],
                "item": [
                    a.link("item", order.item.name, icon="shopping-bag", item_id=order.item.item_id)
                ],
                "component": [
                    a.link("store_settings", order.component.name, icon="cog", store_id=order.order.store_id)
                ],
                "account": order.order.account_id,
                "amount": order.order.amount,
                "campaign": [
                    a.link("campaign", str(order.order.campaign_id), icon="percent",
                           campaign_id=order.order.campaign_id)
                ] if order.order.campaign_id else "No",
                "total": str(order.order.total / 100) + " " + str(order.order.currency),
                "status": [
                    {
                        OrdersModel.STATUS_NEW: a.status("New", "info", "check"),
                        OrdersModel.STATUS_CREATED: a.status("Created", "info", "refresh fa-spin"),
                        OrdersModel.STATUS_SUCCEEDED: a.status("Succeeded", "success", "check"),
                        OrdersModel.STATUS_REJECTED: a.status("Rejected", "danger", "user-times"),
                        OrdersModel.STATUS_ERROR: a.status("Error", "danger", "exclamation-triangle")
                    }.get(order.order.status, a.status(order.order.status, "default", "refresh")),
                ],
                "time": str(order.order.time),
                "id": [
                    a.link("order", order.order.order_id, icon="money", order_id=order.order.order_id)
                ]
            }
            for order in data["orders"]
        ]

        return [
            a.breadcrumbs([
                a.link("stores", "Stores"),
                a.link("store", data["store_name"], store_id=self.context.get("store_id"))
            ], "Orders"),
            a.content("Orders", [
                {
                    "id": "id",
                    "title": "ID"
                }, {
                    "id": "item",
                    "title": "Item"
                }, {
                    "id": "tier",
                    "title": "Tier"
                }, {
                    "id": "time",
                    "title": "Time"
                }, {
                    "id": "account",
                    "title": "Account"
                }, {
                    "id": "amount",
                    "title": "Amount"
                }, {
                    "id": "total",
                    "title": "Total"
                }, {
                    "id": "campaign",
                    "title": "Campaign"
                }, {
                    "id": "status",
                    "title": "Status"
                }], orders, "default", empty="No orders to display."),
            a.pages(data["pages"]),
            a.form("Filters", fields={
                "order_item":
                    a.field("Item", "select", "primary", order=1, values=data["store_items"]),
                "order_tier":
                    a.field("Tier", "select", "primary", order=2, values=data["store_tiers"]),
                "order_account":
                    a.field("Account", "text", "primary", order=3),
                "order_status":
                    a.field("Status", "select", "primary", order=4, values=data["order_statuses"]),
                "order_currency":
                    a.field("Currency", "select", "primary", order=5, values=data["currencies_list"]),
                "order_info":
                    a.field("Info", "json", "primary", order=6, height=100),
            }, methods={
                "filter": a.method("Filter", "primary")
            }, data=data, icon="filter"),
            a.links("Navigate", [
                a.link("store", "Go back", icon="chevron-left", store_id=self.context.get("store_id"))
            ])
        ]

    def access_scopes(self):
        return ["store_admin"]

    async def filter(self, **args):

        store_id = self.context.get("store_id")
        page = self.context.get("page", 1)

        filters = {
            "page": page
        }

        filters.update({
            k: v for k, v in args.items() if v not in ["0", "any"]
        })

        raise a.Redirect("orders", store_id=store_id, **filters)

    @validate(store_id="int", page="int", order_item="int", order_tier="int",
              order_account="int", order_status="str", order_currency="str",
              order_info="load_json_dict")
    async def get(self,
                  store_id,
                  page=1,
                  order_item=None,
                  order_tier=None,
                  order_account=None,
                  order_status=None,
                  order_currency=None,
                  order_info=None):

        stores = self.application.stores
        items = self.application.items
        tiers = self.application.tiers
        currencies = self.application.currencies

        try:
            store = await stores.get_store(self.gamespace, store_id)
        except StoreNotFound:
            raise a.ActionError("No such store")

        try:
            store_items = await items.list_items(self.gamespace, store_id)
        except ItemError as e:
            raise a.ActionError("Failed to list store items: " + e.message)

        try:
            store_tiers = await tiers.list_tiers(self.gamespace, store_id)
        except ItemError as e:
            raise a.ActionError("Failed to list store tiers: " + e.message)

        try:
            currencies_list = await currencies.list_currencies(self.gamespace)
        except CurrencyError as e:
            raise a.ActionError("Failed to list currencies: " + e.message)

        page = to_int(page)

        orders = self.application.orders

        q = orders.orders_query(self.gamespace, store_id)

        q.offset = (page - 1) * OrdersController.ORDERS_PER_PAGE
        q.limit = OrdersController.ORDERS_PER_PAGE

        q.item_id = order_item
        q.tier_id = order_tier
        q.account_id = order_account

        if order_status != "any":
            q.status = order_status

        if order_currency != "any":
            q.currency = order_currency

        if order_info:
            q.info = order_info

        orders, count = await q.query(count=True)
        pages = int(math.ceil(float(count) / float(OrdersController.ORDERS_PER_PAGE)))

        store_items = {
            entry.item.item_id: entry.item.name
            for entry in store_items
        }
        store_items["0"] = "Any"

        store_tiers = {
            tier.tier_id: tier.name
            for tier in store_tiers
        }
        store_tiers["0"] = "Any"

        currencies_list = {
            currency.name: currency.title
            for currency in currencies_list
        }
        currencies_list["any"] = "Any"

        return {
            "orders": orders,
            "pages": pages,
            "order_item": order_item or "0",
            "order_tier": order_tier or "0",
            "order_status": order_status or "any",
            "order_account": order_account or "0",
            "order_currency": order_currency or "any",
            "order_info": order_info or {},
            "store_name": store.name,
            "store_items": store_items,
            "store_tiers": store_tiers,
            "currencies_list": currencies_list,
            "order_statuses": {
                "any": "Any",
                OrdersModel.STATUS_NEW: "New",
                OrdersModel.STATUS_SUCCEEDED: "Succeeded",
                OrdersModel.STATUS_REJECTED: "Rejected",
                OrdersModel.STATUS_ERROR: "Error",
                OrdersModel.STATUS_CREATED: "Created"
            }
        }


class StoreCampaignsController(a.AdminController):
    CAMPAIGNS_PER_PAGE = 20

    @validate(store_id="int")
    async def get(self, store_id, page=1):

        stores = self.application.stores
        campaigns = self.application.campaigns

        offset = (int(page) - 1) * StoreCampaignsController.CAMPAIGNS_PER_PAGE
        limit = StoreCampaignsController.CAMPAIGNS_PER_PAGE

        try:
            store = await stores.get_store(self.gamespace, store_id)
        except StoreNotFound:
            raise a.ActionError("No such store")

        campaigns_list, count = await campaigns.list_campaigns_count(self.gamespace, store_id, offset=offset,
                                                                     limit=limit)

        pages = int(math.ceil(float(count) / float(StoreCampaignsController.CAMPAIGNS_PER_PAGE)))

        result = {
            "campaigns": campaigns_list,
            "store_name": store.name,
            "pages": pages
        }

        return result

    def render(self, data):
        return [
            a.breadcrumbs([
                a.link("stores", "Stores"),
                a.link("store", data["store_name"], store_id=self.context.get("store_id")),
            ], "Campaigns"),
            a.content("Campaigns", [
                {
                    "id": "id",
                    "title": "ID"
                },
                {
                    "id": "name",
                    "title": "Name"
                },
                {
                    "id": "enabled",
                    "title": "Enabled"
                },
                {
                    "id": "dates",
                    "title": "Dates"
                },
                {
                    "id": "actions",
                    "title": "Actions"
                }
            ], [
                          {
                              "id": [a.link("campaign", str(campaign.campaign_id), icon="percent",
                                            campaign_id=campaign.campaign_id)],
                              "name": campaign.name,
                              "dates": "{0} - {1}".format(str(campaign.time_start), str(campaign.time_end)),
                              "enabled": [
                                  a.status("Yes" if campaign.enabled else "No",
                                           "success" if campaign.enabled else "danger")
                              ],
                              "actions": [a.button("campaign", "Delete", "danger", _method="delete",
                                                   campaign_id=campaign.campaign_id)]
                          } for campaign in data["campaigns"]
                      ], "default", empty="No campaigns"),
            a.pages(data["pages"]),

            a.links("Navigate", [
                a.link("store", "Go back", icon="chevron-left", store_id=self.context.get("store_id")),
                a.link("new_campaign", "New Campaign", icon="plus", store_id=self.context.get("store_id"))
            ])
        ]

    def access_scopes(self):
        return ["store_admin"]


class NewStoreCampaignController(a.AdminController):
    @validate(campaign_name="str", campaign_enabled="bool", campaign_time_start="datetime",
              campaign_time_end="datetime", campaign_data="load_json_dict", clone_campaign_items="bool")
    async def create(self, campaign_name, campaign_data, campaign_time_start,
                     campaign_time_end, campaign_enabled=False, clone_campaign_items=False, **ignored):
        stores = self.application.stores
        campaigns = self.application.campaigns

        store_id = self.context.get("store_id")

        try:
            await stores.get_store(self.gamespace, store_id)
        except StoreNotFound:
            raise a.ActionError("No such store")

        try:
            campaign_id = await campaigns.new_campaign(
                self.gamespace, store_id, campaign_name, campaign_time_start, campaign_time_end,
                campaign_data, campaign_enabled)
        except ItemError as e:
            raise a.ActionError(e.message)

        clone = self.context.get("clone")

        if clone_campaign_items and clone:
            try:
                await campaigns.clone_campaign_items(self.gamespace, clone, campaign_id)
            except CampaignError:
                pass

        raise a.Redirect(
            "campaign",
            message="New campaign has been created",
            campaign_id=campaign_id)

    @validate(store_id="int", clone="int")
    async def get(self, store_id, clone=None):

        stores = self.application.stores
        campaigns = self.application.campaigns

        try:
            store = await stores.get_store(self.gamespace, store_id)
        except StoreNotFound:
            raise a.ActionError("No such store")

        if clone:
            try:
                campaign = await campaigns.get_campaign(self.gamespace, clone)
            except CampaignNotFound:
                raise a.ActionError("No campaign to clone from")
            except CampaignError as e:
                raise a.ActionError("Failed to clone campaign: " + e.message)

            if str(campaign.store_id) != str(store_id):
                raise a.ActionError("Cannot clone a campaign from different store")

            campaign_name = campaign.name
            campaign_data = campaign.data
            campaign_enabled = campaign.enabled
            campaign_time_start = campaign.time_start
            campaign_time_end = campaign.time_end
        else:
            campaign_name = ""
            campaign_data = {}
            campaign_enabled = True
            campaign_time_start = datetime.datetime.utcnow()
            campaign_time_end = datetime.datetime.utcnow()

        campaign_scheme = store.campaign_scheme or {}

        data = {
            "clone": bool(clone),
            "store_name": store.name,
            "campaign_name": campaign_name,
            "campaign_data": campaign_data,
            "campaign_time_start": str(campaign_time_start),
            "campaign_time_end": str(campaign_time_end),
            "campaign_scheme": campaign_scheme,
            "campaign_enabled": "true" if campaign_enabled else "false",
            "clone_campaign_items": "true"
        }

        return data

    def render(self, data):

        fields = {
            "campaign_name": a.field(
                "Campaign Name", "text", "primary", "non-empty",
                order=1, description="Used to identify the campaign in the admin tool, "
                                     "this name is not sent to the users."),
            "campaign_enabled": a.field(
                "Is Campaign Enabled?", "switch", "primary",
                order=2, description="Only enabled campaigns will be active."),
            "campaign_data": a.field(
                "Campaign Custom Payload", "dorn", "primary",
                schema=data["campaign_scheme"], order=4),
            "campaign_time_start": a.field("Start date", "date", "primary", "non-empty", order=5),
            "campaign_time_end": a.field("End date", "date", "primary", "non-empty", order=6)
        }

        if data["clone"]:
            fields["clone_campaign_items"] = a.field(
                "Clone campaign items?", "switch", "primary",
                order=3, description=u"Copy the items from the "
                                     u"campaign <b>{0}</b> to the new one".format(data["campaign_name"]))

        return [
            a.breadcrumbs([
                a.link("stores", "Stores"),
                a.link("store", data["store_name"], store_id=self.context.get("store_id")),
                a.link("campaigns", "Campaigns", store_id=self.context.get("store_id")),
            ], "New campaign"),
            a.form("New campaign", fields=fields, methods={
                "create": a.method("Clone" if self.context.get("clone") else "Create", "primary")
            }, data=data),
            a.links("Navigate", [
                a.link("campaigns", "Go back", icon="chevron-left", store_id=self.context.get("store_id")),
                a.link("store_settings", "Edit Custom Payload Scheme", icon="list-alt",
                       store_id=self.context.get("store_id"))
            ])
        ]

    def access_scopes(self):
        return ["store_admin"]


class StoreCampaignController(a.AdminController):
    @validate(campaign_name="str", campaign_enabled="bool", campaign_time_start="datetime",
              campaign_time_end="datetime", campaign_data="load_json_dict")
    async def update(self, campaign_name, campaign_data, campaign_time_start,
                     campaign_time_end, campaign_enabled=False, **ignored):

        campaigns = self.application.campaigns
        campaign_id = self.context.get("campaign_id")

        try:
            updated = await campaigns.update_campaign(
                self.gamespace, campaign_id, campaign_name, campaign_time_start, campaign_time_end,
                campaign_data, campaign_enabled)
        except ItemError as e:
            raise a.ActionError(e.message)

        raise a.Redirect(
            "campaign",
            message="Campaign has been updated" if updated else "Nothing to update",
            campaign_id=campaign_id)

    async def delete(self, **ignored):

        campaigns = self.application.campaigns
        campaign_id = self.context.get("campaign_id")

        try:
            campaign = await campaigns.get_campaign(self.gamespace, campaign_id)
        except CampaignNotFound:
            raise a.ActionError("No such campaign")
        except CampaignError as e:
            raise a.ActionError("Failed to get campaign: " + e.message)

        try:
            deleted = await campaigns.delete_campaign(
                self.gamespace, campaign_id)
        except ItemError as e:
            raise a.ActionError(e.message)

        raise a.Redirect(
            "campaigns",
            message="Campaign has been deleted" if deleted else "Nothing to delete",
            store_id=campaign.store_id)

    @validate(campaign_id="int")
    async def get(self, campaign_id):

        stores = self.application.stores
        campaigns = self.application.campaigns

        try:
            campaign = await campaigns.get_campaign(self.gamespace, campaign_id)
        except CampaignNotFound:
            raise a.ActionError("No such campaign")
        except CampaignError as e:
            raise a.ActionError("Failed to get campaign: " + e.message)

        try:
            store = await stores.get_store(self.gamespace, campaign.store_id)
        except StoreNotFound:
            raise a.ActionError("No such store")

        try:
            campaign_items = await campaigns.list_campaign_items(self.gamespace, campaign_id)
        except CampaignError as e:
            raise a.ActionError(e.message)

        data = {
            "store_name": store.name,
            "store_id": campaign.store_id,
            "campaign_name": campaign.name,
            "campaign_data": campaign.data,
            "campaign_time_start": str(campaign.time_start),
            "campaign_time_end": str(campaign.time_end),
            "campaign_items": campaign_items,
            "campaign_scheme": store.campaign_scheme or {},
            "campaign_enabled": "true" if campaign.enabled else "false"
        }

        return data

    def render(self, data):
        return [
            a.breadcrumbs([
                a.link("stores", "Stores"),
                a.link("store", data["store_name"], store_id=data["store_id"]),
                a.link("campaigns", "Campaigns", store_id=data["store_id"]),
            ], data["campaign_name"]),
            a.content("Campaign Items", [
                {
                    "id": "name",
                    "title": "Name"
                },
                {
                    "id": "original_tier",
                    "title": "Original Tier"
                },
                {
                    "id": "updated_tier",
                    "title": "Updated Tier"
                },
                {
                    "id": "updated_public",
                    "title": "Public Item Properties Diff"
                },
                {
                    "id": "updated_private",
                    "title": "Private Item Properties Diff"
                },
                {
                    "id": "actions",
                    "title": "Actions"
                }
            ], [
                          {
                              "name": [a.link("campaign_item", str(entry.item.name), icon="shopping-bag",
                                              item_id=entry.item.item_id, campaign_id=self.context.get("campaign_id"))],
                              "original_tier": [a.link("tier", str(entry.tier.title), tier_id=entry.tier.tier_id)],
                              "updated_tier": [
                                  a.link("tier", str(entry.campaign_tier_title), tier_id=entry.campaign_tier_id)],
                              "updated_public": [
                                  a.json_view({
                                      "updated": entry.campaign_item.public_data,
                                      "old": entry.item.public_data
                                  })
                              ], "updated_private": [
                              a.json_view({
                                  "updated": entry.campaign_item.private_data,
                                  "old": entry.item.private_data
                              })
                          ],
                              "actions": [a.button("campaign_item", "Remove", "danger", _method="remove",
                                                   campaign_id=self.context.get("campaign_id"),
                                                   item_id=entry.item.item_id)]
                          } for entry in data["campaign_items"]
                      ], "default", empty="No campaign items so far"),
            a.links("Actions", [
                a.link("new_campaign_item_select", "Add an item into the campaign", icon="plus",
                       campaign_id=self.context.get("campaign_id"))
            ]),
            a.form("Campaign", fields={
                "campaign_name": a.field(
                    "Campaign Name", "text", "primary", "non-empty",
                    order=1, description="Used to identify the campaign in the admin tool, "
                                         "this name is not sent to the users."),
                "campaign_enabled": a.field(
                    "Is Campaign Enabled?", "switch", "primary",
                    order=2, description="Only enabled campaigns will be active."),
                "campaign_data": a.field(
                    "Campaign Custom Payload", "dorn", "primary",
                    schema=data["campaign_scheme"], order=3),
                "campaign_time_start": a.field("Start date", "date", "primary", "non-empty", order=4),
                "campaign_time_end": a.field("End date", "date", "primary", "non-empty", order=5)
            }, methods={
                "update": a.method("Update", "primary"),
                "delete": a.method("Delete", "danger"),
            }, data=data),
            a.links("Navigate", [
                a.link("campaigns", "Go back", icon="chevron-left", store_id=data["store_id"]),
                a.link("store_settings", "Edit Custom Payload Scheme", icon="list-alt", store_id=data["store_id"]),
                a.link("new_campaign", "Clone Campaign", icon="clone",
                       clone=self.context.get("campaign_id"),
                       store_id=data["store_id"])
            ])
        ]

    def access_scopes(self):
        return ["store_admin"]


class NewCampaignItemSelectController(a.AdminController):
    @validate(campaign_id="int")
    async def get(self, campaign_id):

        stores = self.application.stores
        items = self.application.items
        campaigns = self.application.campaigns

        try:
            campaign = await campaigns.get_campaign(self.gamespace, campaign_id)
        except CampaignNotFound:
            raise a.ActionError("No such campaign")
        except CampaignError as e:
            raise a.ActionError("Failed to get a campaign: " + e.message)

        store_id = campaign.store_id

        try:
            store = await stores.get_store(self.gamespace, store_id)
        except StoreNotFound:
            raise a.ActionError("No such store")

        try:
            store_items_raw = await items.list_enabled_items(self.gamespace, store_id)
        except ItemError as e:
            raise a.ActionError(e.message)
        else:
            store_items = {
                str(entry.item.item_id): entry
                for entry in store_items_raw
            }

        try:
            existing_items_raw = await campaigns.list_campaign_items(self.gamespace, campaign_id)
        except CampaignError as e:
            raise a.ActionError(e.message)
        else:
            existing_items = set(
                str(entry.item.item_id)
                for entry in existing_items_raw
            )

        for existing_item_id in existing_items:
            store_items.pop(existing_item_id, None)

        store_items = sorted(store_items.values(), key=lambda entry: (int(entry.item.item_id), entry,))

        data = {
            "store_name": store.name,
            "store_id": store_id,
            "campaign_name": campaign.name,
            "store_items": store_items
        }

        return data

    def render(self, data):
        return [
            a.breadcrumbs([
                a.link("stores", "Stores"),
                a.link("store", data["store_name"], store_id=data["store_id"]),
                a.link("campaigns", "Campaigns", store_id=data["store_id"]),
                a.link("campaign", data["campaign_name"], campaign_id=self.context.get("campaign_id")),
            ], "Add Item"),

            a.content("Select Item", [
                {
                    "id": "name",
                    "title": "Select"
                },
                {
                    "id": "title",
                    "title": "Title"
                },
                {
                    "id": "category",
                    "title": "Category"
                },
                {
                    "id": "tier",
                    "title": "Current Tier"
                }
            ], [
                          {
                              "name": [
                                  a.link("new_campaign_item", entry.item.name, icon="plus",
                                         item_id=entry.item.item_id, campaign_id=self.context.get("campaign_id"))],
                              "category": [
                                  a.link(
                                      "category", entry.category.name,
                                      icon="list-alt", category_id=entry.category.category_id)
                              ],
                              "tier": [a.link("tier", entry.tier.title, tier_id=entry.tier.tier_id)],
                              "title": entry.item.title("EN")
                          }
                          for entry in data["store_items"]
                      ], "default"),

            a.links("Navigate", [
                a.link("campaign", "Go back", icon="chevron-left", campaign_id=self.context.get("campaign_id"))
            ])
        ]

    def access_scopes(self):
        return ["store_admin"]


class NewCampaignItemController(a.AdminController):
    @validate(campaign_item_tier="int",
              campaign_item_public_data="load_json_dict",
              campaign_item_private_data="load_json_dict")
    async def create(self, campaign_item_tier, campaign_item_public_data, campaign_item_private_data, **ignored):

        campaign_id = self.context.get("campaign_id")
        item_id = self.context.get("item_id")

        stores = self.application.stores
        items = self.application.items
        campaigns = self.application.campaigns

        async with self.application.db.acquire() as db:
            try:
                campaign = await campaigns.get_campaign(self.gamespace, campaign_id, db=db)
            except CampaignNotFound:
                raise a.ActionError("No such campaign")
            except CampaignError as e:
                raise a.ActionError("Failed to get a campaign: " + e.message)

            try:
                item = await items.get_item(self.gamespace, item_id, db=db)
            except ItemNotFound:
                raise a.ActionError("No such item")
            except ItemError as e:
                raise a.ActionError("Failed to get an item: " + e.message)

            if str(campaign.store_id) != str(item.store_id):
                raise a.ActionError("Campaign and item do not share store")

            store_id = campaign.store_id

            try:
                await stores.get_store(self.gamespace, store_id, db=db)
            except StoreNotFound:
                raise a.ActionError("No such store")

            try:
                await campaigns.add_campaign_item(
                    self.gamespace, campaign_id, item_id, campaign_item_private_data,
                    campaign_item_public_data, campaign_item_tier)
            except CampaignError as e:
                raise a.ActionError(e.message)

            raise a.Redirect("campaign", message="Item has been added into the campaign",
                             campaign_id=campaign_id)

    @validate(campaign_id="int", item_id="int")
    async def get(self, campaign_id, item_id):

        stores = self.application.stores
        items = self.application.items
        campaigns = self.application.campaigns
        tiers = self.application.tiers
        categories = self.application.categories

        async with self.application.db.acquire() as db:
            try:
                campaign = await campaigns.get_campaign(self.gamespace, campaign_id, db=db)
            except CampaignNotFound:
                raise a.ActionError("No such campaign")
            except CampaignError as e:
                raise a.ActionError("Failed to get a campaign: " + e.message)

            try:
                item = await items.get_item(self.gamespace, item_id, db=db)
            except ItemNotFound:
                raise a.ActionError("No such item")
            except ItemError as e:
                raise a.ActionError("Failed to get an item: " + e.message)

            try:
                category = await categories.get_category(self.gamespace, item.category, db=db)
            except CategoryNotFound:
                raise a.ActionError("No such category")

            if str(campaign.store_id) != str(item.store_id):
                raise a.ActionError("Campaign and item do not share store")

            store_id = campaign.store_id

            try:
                store = await stores.get_store(self.gamespace, store_id, db=db)
            except StoreNotFound:
                raise a.ActionError("No such store")

            try:
                tiers_list = await tiers.list_tiers(self.gamespace, store_id, db=db)
            except TierError as e:
                raise a.ActionError(e.message)

            try:
                common_scheme = await categories.get_common_scheme(self.gamespace)
            except CategoryNotFound:
                common_public_item_scheme = {}
                common_private_item_scheme = {}
            else:
                common_public_item_scheme = common_scheme.public_item_scheme
                common_private_item_scheme = common_scheme.private_item_scheme

            public_item_scheme = category.public_item_scheme
            private_item_scheme = category.private_item_scheme

            common_update(public_item_scheme, common_public_item_scheme)
            common_update(private_item_scheme, common_private_item_scheme)

            data = {
                "store_name": store.name,
                "store_id": store_id,
                "campaign_name": campaign.name,
                "item_name": item.name,
                "campaign_item_public_data": item.public_data,
                "campaign_item_private_data": item.private_data,
                "public_item_scheme": public_item_scheme,
                "private_item_scheme": private_item_scheme,
                "campaign_item_tier": item.tier,
                "tiers_list": {tier.tier_id: u"{0} ({1})".format(tier.title, tier.name) for tier in tiers_list},
            }

            return data

    def render(self, data):
        return [
            a.breadcrumbs([
                a.link("stores", "Stores"),
                a.link("store", data["store_name"], store_id=data["store_id"]),
                a.link("campaigns", "Campaigns", store_id=data["store_id"]),
                a.link("campaign", data["campaign_name"], campaign_id=self.context.get("campaign_id")),
            ], u"Add Item: {0}".format(data["item_name"])),

            a.form(u"Add an item <b>{0}</b> into a campaign <b>{1}</b>".format(
                data["item_name"], data["campaign_name"]), fields={
                "campaign_item_tier": a.field(
                    "Updated Price Tier", "select", "primary",
                    values=data["tiers_list"], order=1),
                "campaign_item_public_data": a.field(
                    "Updated Public Item Properties", "dorn", "primary",
                    schema=data["public_item_scheme"], order=4, description="Available to everyone"),
                "campaign_item_private_data": a.field(
                    "Updated Private Item Properties", "dorn", "primary",
                    schema=data["private_item_scheme"], order=5,
                    description="Available only as a response to successful purchase")
            }, methods={
                "create": a.method("Add the Item To the Campaign", "primary"),
            }, data=data),

            a.links("Navigate", [
                a.link("campaign", "Go back", icon="chevron-left", campaign_id=self.context.get("campaign_id"))
            ])
        ]

    def access_scopes(self):
        return ["store_admin"]


class CampaignItemController(a.AdminController):
    @validate(campaign_item_tier="int",
              campaign_item_public_data="load_json_dict",
              campaign_item_private_data="load_json_dict")
    async def update(self, campaign_item_tier, campaign_item_public_data, campaign_item_private_data, **ignored):

        campaign_id = self.context.get("campaign_id")
        item_id = self.context.get("item_id")

        stores = self.application.stores
        items = self.application.items
        campaigns = self.application.campaigns

        async with self.application.db.acquire() as db:
            try:
                campaign = await campaigns.get_campaign(self.gamespace, campaign_id, db=db)
            except CampaignNotFound:
                raise a.ActionError("No such campaign")
            except CampaignError as e:
                raise a.ActionError("Failed to get a campaign: " + e.message)

            try:
                item = await items.get_item(self.gamespace, item_id, db=db)
            except ItemNotFound:
                raise a.ActionError("No such item")
            except ItemError as e:
                raise a.ActionError("Failed to get an item: " + e.message)

            if str(campaign.store_id) != str(item.store_id):
                raise a.ActionError("Campaign and item do not share store")

            store_id = campaign.store_id

            try:
                await stores.get_store(self.gamespace, store_id, db=db)
            except StoreNotFound:
                raise a.ActionError("No such store")

            try:
                updated = await campaigns.update_campaign_item(
                    self.gamespace, campaign_id, item_id, campaign_item_private_data,
                    campaign_item_public_data, campaign_item_tier)
            except CampaignError as e:
                raise a.ActionError(e.message)

            raise a.Redirect("campaign",
                             message="Item has been updated" if updated else "Nothing to update",
                             campaign_id=campaign_id)

    async def remove(self, **ignored):

        campaign_id = self.context.get("campaign_id")
        item_id = self.context.get("item_id")

        stores = self.application.stores
        items = self.application.items
        campaigns = self.application.campaigns

        async with self.application.db.acquire() as db:
            try:
                campaign = await campaigns.get_campaign(self.gamespace, campaign_id, db=db)
            except CampaignNotFound:
                raise a.ActionError("No such campaign")
            except CampaignError as e:
                raise a.ActionError("Failed to get a campaign: " + e.message)

            try:
                item = await items.get_item(self.gamespace, item_id, db=db)
            except ItemNotFound:
                raise a.ActionError("No such item")
            except ItemError as e:
                raise a.ActionError("Failed to get an item: " + e.message)

            if str(campaign.store_id) != str(item.store_id):
                raise a.ActionError("Campaign and item do not share store")

            store_id = campaign.store_id

            try:
                await stores.get_store(self.gamespace, store_id, db=db)
            except StoreNotFound:
                raise a.ActionError("No such store")

            try:
                deleted = await campaigns.delete_campaign_item(
                    self.gamespace, campaign_id, item_id, )
            except CampaignError as e:
                raise a.ActionError(e.message)

            raise a.Redirect("campaign",
                             message="Item has been removed from campaign" if deleted else "Nothing to remove",
                             campaign_id=campaign_id)

    @validate(campaign_id="int", item_id="int")
    async def get(self, campaign_id, item_id):

        stores = self.application.stores
        items = self.application.items
        campaigns = self.application.campaigns
        tiers = self.application.tiers
        categories = self.application.categories

        async with self.application.db.acquire() as db:
            try:
                campaign_item = await campaigns.get_campaign_item(self.gamespace, campaign_id, item_id, db=db)
            except CampaignItemNotFound:
                raise a.ActionError("No such campaign item")
            except CampaignError as e:
                raise a.ActionError("Failed to get a campaign item: " + e.message)

            try:
                campaign = await campaigns.get_campaign(self.gamespace, campaign_id, db=db)
            except CampaignNotFound:
                raise a.ActionError("No such campaign")
            except CampaignError as e:
                raise a.ActionError("Failed to get a campaign: " + e.message)

            try:
                item = await items.get_item(self.gamespace, item_id, db=db)
            except ItemNotFound:
                raise a.ActionError("No such item")
            except ItemError as e:
                raise a.ActionError("Failed to get an item: " + e.message)

            try:
                category = await categories.get_category(self.gamespace, item.category, db=db)
            except CategoryNotFound:
                raise a.ActionError("No such category")

            if str(campaign.store_id) != str(item.store_id):
                raise a.ActionError("Campaign and item do not share store")

            store_id = campaign.store_id

            try:
                store = await stores.get_store(self.gamespace, store_id, db=db)
            except StoreNotFound:
                raise a.ActionError("No such store")

            try:
                tiers_list = await tiers.list_tiers(self.gamespace, store_id, db=db)
            except TierError as e:
                raise a.ActionError(e.message)

            try:
                common_scheme = await categories.get_common_scheme(self.gamespace)
            except CategoryNotFound:
                common_public_item_scheme = {}
                common_private_item_scheme = {}
            else:
                common_public_item_scheme = common_scheme.public_item_scheme
                common_private_item_scheme = common_scheme.private_item_scheme

            public_item_scheme = category.public_item_scheme
            private_item_scheme = category.private_item_scheme

            common_update(public_item_scheme, common_public_item_scheme)
            common_update(private_item_scheme, common_private_item_scheme)

            data = {
                "store_name": store.name,
                "store_id": store_id,
                "campaign_name": campaign.name,
                "item_name": item.name,
                "campaign_item_public_data": campaign_item.public_data,
                "campaign_item_private_data": campaign_item.private_data,
                "campaign_item_tier": campaign_item.tier,
                "public_item_scheme": public_item_scheme,
                "private_item_scheme": private_item_scheme,
                "tiers_list": {tier.tier_id: u"{0} ({1})".format(tier.title, tier.name) for tier in tiers_list},
            }

            return data

    def render(self, data):
        return [
            a.breadcrumbs([
                a.link("stores", "Stores"),
                a.link("store", data["store_name"], store_id=data["store_id"]),
                a.link("campaigns", "Campaigns", store_id=data["store_id"]),
                a.link("campaign", data["campaign_name"], campaign_id=self.context.get("campaign_id")),
            ], u"Update Item: {0}".format(data["item_name"])),

            a.form(u"Update an item <b>{0}</b> in campaign <b>{1}</b>".format(
                data["item_name"], data["campaign_name"]), fields={
                "campaign_item_tier": a.field(
                    "Updated Price Tier", "select", "primary",
                    values=data["tiers_list"], order=1),
                "campaign_item_public_data": a.field(
                    "Updated Public Item Properties", "dorn", "primary",
                    schema=data["public_item_scheme"], order=4, description="Available to everyone"),
                "campaign_item_private_data": a.field(
                    "Updated Private Item Properties", "dorn", "primary",
                    schema=data["private_item_scheme"], order=5,
                    description="Available only as a response to successful purchase")
            }, methods={
                "update": a.method("Update an Item in the Campaign", "primary", order=2),
                "remove": a.method("Remove from Campaign", "danger", order=1),
            }, data=data),

            a.links("Navigate", [
                a.link("campaign", "Go back", icon="chevron-left", campaign_id=self.context.get("campaign_id"))
            ])
        ]

    def access_scopes(self):
        return ["store_admin"]


def init():
    from . import appstore
    from . import steam
    from . import xsolla
    from . import mailru
