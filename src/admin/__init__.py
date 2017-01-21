# coding=utf-8

from tornado.gen import coroutine, Return

import common.admin as a
import common
import ujson
import math

from model.content import ContentError, ContentNotFound
from model.store import StoreError, StoreNotFound, StoreComponentNotFound
from model.category import CategoryError, CategoryNotFound
from model.item import ItemError, ItemNotFound
from model.billing import OfflineBillingMethod, IAPBillingMethod
from model.tier import TierModel, TierError, TierNotFound, CurrencyError, CurrencyNotFound
from model.order import OrderQueryError, OrdersModel


class StoreAdminComponents(object):
    COMPONENTS = {}

    @staticmethod
    def component(component_name, action, store_id):
        return StoreAdminComponents.COMPONENTS[component_name](component_name, action, store_id)

    @staticmethod
    def components():
        return StoreAdminComponents.COMPONENTS.keys()

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
        return TierAdminComponents.COMPONENTS.keys()

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

    @coroutine
    def init(self):
        pass

    def load(self, data):
        self.component.load(data)

    def render(self):
        return {
            "product": a.field("Product ID", "text", "primary", "non-empty")
        }

    def update(self, product, **fields):
        self.component.product = product


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

    @coroutine
    def init(self):
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


class BillingMethodAdmin(object):
    def __init__(self, action, store_id, method_class):
        self.action = action
        self.store_id = store_id
        self.method = method_class()

    def dump(self):
        return self.method.dump()

    def get(self):
        raise NotImplementedError()

    @coroutine
    def init(self):
        pass

    def load(self, data):
        self.method.load(data)

    def render(self):
        raise NotImplementedError()

    def update(self, **fields):
        raise NotImplementedError()


class CategoriesController(a.AdminController):
    @coroutine
    def get(self):
        categories = self.application.categories
        items = yield categories.list_categories(self.gamespace)

        result = {
            "items": items
        }

        raise a.Return(result)

    def render(self, data):
        return [
            a.breadcrumbs([], "Categories"),
            a.links("Items", [
                a.link("category", item.name, icon="list-alt", category_id=item.category_id)
                for item in data["items"]
                ]),
            a.links("Navigate", [
                a.link("index", "Go back"),
                a.link("new_category", "Create category", icon="plus"),
                a.link("category_common", "Edit common scheme")
            ])
        ]

    def access_scopes(self):
        return ["store_admin"]


class CategoryCommonController(a.AdminController):
    @coroutine
    def get(self):

        categories = self.application.categories

        try:
            common_scheme = yield categories.get_common_scheme(self.gamespace)
        except CategoryNotFound:
            common_scheme = {}

        result = {
            "scheme": common_scheme
        }

        raise a.Return(result)

    def render(self, data):
        return [
            a.breadcrumbs([
                a.link("categories", "Categories")
            ], "Common scheme"),
            a.form("Common scheme shared across categories", fields={
                "scheme": a.field("Scheme", "json", "primary", "non-empty")
            }, methods={
                "update": a.method("Update", "primary")
            }, data=data),
            a.links("Navigate", [
                a.link("categories", "Go back"),
                a.link("https://spacetelescope.github.io/understanding-json-schema/index.html", "See docs", icon="book")
            ])
        ]

    def access_scopes(self):
        return ["store_admin"]

    @coroutine
    def update(self, scheme):

        try:
            scheme = ujson.loads(scheme)
        except (KeyError, ValueError):
            raise a.ActionError("Corrupted JSON")

        categories = self.application.categories

        try:
            yield categories.update_common_scheme(self.gamespace, scheme)
        except CategoryError as e:
            raise a.ActionError("Failed to update common scheme: " + e.args[0])

        raise a.Redirect("category_common", message="Common scheme has been updated")


class CategoryController(a.AdminController):
    @coroutine
    def delete(self, **ignored):

        category_id = self.context.get("category_id")
        categories = self.application.categories

        try:
            yield categories.delete_category(self.gamespace, category_id)
        except CategoryError as e:
            raise a.ActionError("Failed to delete category: " + e.args[0])

        raise a.Redirect(
            "categories",
            message="Category has been deleted")

    @coroutine
    def get(self, category_id):

        categories = self.application.categories

        try:
            category = yield categories.get_category(self.gamespace, category_id)
        except CategoryNotFound:
            raise a.ActionError("No such category")

        result = {
            "category_name": category.name,
            "category_scheme": category.scheme
        }

        raise a.Return(result)

    def render(self, data):
        return [
            a.breadcrumbs([
                a.link("categories", "Categories")
            ], "Category"),
            a.form("Update category", fields={
                "category_name": a.field("Category unique ID", "text", "primary", "non-empty"),
                "category_scheme": a.field("Category scheme", "json", "primary", "non-empty")
            }, methods={
                "update": a.method("Update", "primary"),
                "delete": a.method("Delete this category", "danger")
            }, data=data),
            a.links("Navigate", [
                a.link("categories", "Go back"),
                a.link("category_common", "Edit common scheme"),
                a.link("https://spacetelescope.github.io/understanding-json-schema/index.html", "See docs", icon="book")
            ])
        ]

    def access_scopes(self):
        return ["store_admin"]

    @coroutine
    def update(self, category_name, category_scheme):

        category_id = self.context.get("category_id")

        try:
            category_scheme = ujson.loads(category_scheme)
        except (KeyError, ValueError):
            raise a.ActionError("Corrupted JSON")

        categories = self.application.categories

        try:
            yield categories.update_category(self.gamespace, category_id, category_name, category_scheme)
        except CategoryError as e:
            raise a.ActionError("Failed to update category: " + e.args[0])

        raise a.Redirect(
            "category",
            message="Category has been updated",
            category_id=category_id)


class ChooseCategoryController(a.AdminController):
    @coroutine
    def apply(self, category, billing_method):
        raise a.Redirect(
            "new_item",
            store_id=self.context.get("store_id"),
            category_id=category, billing_method=billing_method)

    @coroutine
    def get(self, store_id):
        categories = yield self.application.categories.list_categories(self.gamespace)

        try:
            store = yield self.application.stores.get_store(self.gamespace, store_id)
        except StoreNotFound:
            raise a.ActionError("No such store")

        raise Return({
            "store_name": store.name,
            "categories": {
                category.category_id: category.name for category in categories
            }
        })

    def render(self, data):
        return [
            a.breadcrumbs([
                a.link("stores", "Stores"),
                a.link("store", data["store_name"], store_id=self.context.get("store_id")),
            ], "Choose category"),
            a.form(
                title="Choose category and billing method",
                fields={
                    "category": a.field(
                        "Select category", "select", "primary", values=data["categories"]
                    ),
                    "billing_method": a.field(
                        "Billing method", "select", "primary", values={
                            method: method for method in BillingMethods.methods()
                        }
                    )
                }, methods={
                    "apply": a.method("Proceed", "primary")
                }, data=data
            ),
            a.links("Navigation", links=[
                a.link("stores", "Go back"),
                a.link("categories", "Manage categories", "list-alt")
            ])
        ]

    def access_scopes(self):
        return ["store_admin"]


class ContentController(a.AdminController):
    @coroutine
    def delete(self, **ignored):

        content_id = self.context.get("content_id")
        contents = self.application.contents

        try:
            yield contents.delete_content(self.gamespace, content_id)
        except ContentError as e:
            raise a.ActionError("Failed to delete content: " + e.args[0])

        raise a.Redirect("contents", message="Content has been deleted")

    @coroutine
    def get(self, content_id):

        contents = self.application.contents

        try:
            content = yield contents.get_content(self.gamespace, content_id)
        except ContentNotFound:
            raise a.ActionError("No such content")

        result = {
            "content_name": content.name,
            "content_json": content.data
        }

        raise a.Return(result)

    def render(self, data):
        return [
            a.breadcrumbs([
                a.link("contents", "Contents")
            ], "Content"),
            a.form("Update content", fields={
                "content_name": a.field("Content unique ID", "text", "primary", "non-empty"),
                "content_json": a.field("Content payload (any useful data)", "json", "primary", "non-empty")
            }, methods={
                "update": a.method("Update", "primary"),
                "delete": a.method("Delete this content", "danger")
            }, data=data),
            a.links("Navigate", [
                a.link("contents", "Go back")
            ])
        ]

    def access_scopes(self):
        return ["store_admin"]

    @coroutine
    def update(self, content_name, content_json):

        content_id = self.context.get("content_id")

        try:
            content_json = ujson.loads(content_json)
        except (KeyError, ValueError):
            raise a.ActionError("Corrupted JSON")

        contents = self.application.contents

        try:
            yield contents.update_content(self.gamespace, content_id, content_name, content_json)
        except ContentError as e:
            raise a.ActionError("Failed to update content: " + e.args[0])

        raise a.Redirect(
            "content",
            message="Content has been updated",
            content_id=content_id)


class ContentsController(a.AdminController):
    @coroutine
    def get(self):
        contents = self.application.contents
        items = yield contents.list_contents(self.gamespace)

        result = {
            "items": items
        }

        raise a.Return(result)

    def render(self, data):
        return [
            a.breadcrumbs([], "Contents"),
            a.links("Items", [
                a.link("content", item.name, icon="paper-plane", content_id=item.content_id)
                for item in data["items"]
                ]),
            a.links("Navigate", [
                a.link("index", "Go back"),
                a.link("new_content", "Create content", icon="plus")
            ])
        ]

    def access_scopes(self):
        return ["store_admin"]


class CurrenciesController(a.AdminController):
    @coroutine
    def get(self):
        currencies = self.application.currencies
        items = yield currencies.list_currencies(self.gamespace)

        result = {
            "items": items
        }

        raise a.Return(result)

    def render(self, data):
        return [
            a.breadcrumbs([], "Currencies"),
            a.links("Items", [
                a.link("currency", item.title + u"({0})".format(item.symbol),
                       icon="bitcoin", currency_id=item.currency_id)
                for item in data["items"]
                ]),
            a.links("Navigate", [
                a.link("index", "Go back"),
                a.link("new_currency", "Create currency", icon="plus")
            ])
        ]

    def access_scopes(self):
        return ["store_admin"]


class CurrencyController(a.AdminController):
    @coroutine
    def delete(self, **ignored):

        currency_id = self.context.get("currency_id")
        currencies = self.application.currencies

        try:
            yield currencies.delete_currency(self.gamespace, currency_id)
        except CurrencyError as e:
            raise a.ActionError("Failed to delete currency: " + e.args[0])

        raise a.Redirect("currencies", message="Currency has been deleted")

    @coroutine
    def get(self, currency_id):

        currencies = self.application.currencies

        try:
            content = yield currencies.get_currency(self.gamespace, currency_id)
        except CurrencyNotFound:
            raise a.ActionError("No such currency")

        result = {
            "currency_name": content.name,
            "currency_title": content.title,
            "currency_format": content.format,
            "currency_symbol": content.symbol,
            "currency_label": content.label
        }

        raise a.Return(result)

    def render(self, data):
        return [
            a.breadcrumbs([
                a.link("currencies", "Currencies")
            ], "Currency"),
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
                a.link("currencies", "Go back")
            ])
        ]

    def access_scopes(self):
        return ["store_admin"]

    @coroutine
    def update(self, currency_name, currency_title, currency_format, currency_symbol, currency_label):

        currency_id = self.context.get("currency_id")

        currencies = self.application.currencies

        try:
            yield currencies.update_currency(self.gamespace, currency_id, currency_name, currency_title,
                                             currency_format, currency_symbol, currency_label)
        except CurrencyError as e:
            raise a.ActionError("Failed to update currency: " + e.args[0])

        raise a.Redirect(
            "currency",
            message="Currency has been updated",
            currency_id=currency_id)


class IAPBillingMethodAdmin(BillingMethodAdmin):
    def __init__(self, action, store_id):
        super(IAPBillingMethodAdmin, self).__init__(action, store_id, IAPBillingMethod)
        self.items = []

    def get(self):
        return {
            "tier": self.method.tier
        }

    @coroutine
    def init(self):
        self.items = yield self.action.application.tiers.list_tiers(self.action.gamespace, self.store_id)

    def render(self):

        tiers = {
            item.name: item.name for item in self.items
        }
        tiers[""] = "Not selected yet"

        return {
            "tier": a.field("Tier", "select", "primary", "non-empty", values=tiers)
        }

    def update(self, tier):
        self.method.tier = tier


class NewCategoryController(a.AdminController):
    @coroutine
    def create(self, category_name, category_scheme):

        try:
            category_scheme = ujson.loads(category_scheme)
        except (KeyError, ValueError):
            raise a.ActionError("Corrupted JSON")

        categories = self.application.categories

        try:
            category_id = yield categories.new_category(self.gamespace, category_name, category_scheme)
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
                "category_name": a.field("Category unique ID", "text", "primary", "non-empty"),
                "category_scheme": a.field("Category scheme", "json", "primary", "non-empty")
            }, methods={
                "create": a.method("Create", "primary")
            }, data=data),
            a.links("Navigate", [
                a.link("categories", "Go back"),
                a.link("https://spacetelescope.github.io/understanding-json-schema/index.html", "See docs", icon="book")
            ])
        ]

    def access_scopes(self):
        return ["store_admin"]


class NewContentController(a.AdminController):
    @coroutine
    def create(self, content_name, content_json):

        try:
            content_json = ujson.loads(content_json)
        except (KeyError, ValueError):
            raise a.ActionError("Corrupted JSON")

        contents = self.application.contents

        try:
            content_id = yield contents.new_content(self.gamespace, content_name, content_json)
        except ContentError as e:
            raise a.ActionError("Failed to create new content: " + e.args[0])

        raise a.Redirect(
            "content",
            message="New content has been created",
            content_id=content_id)

    def render(self, data):
        return [
            a.breadcrumbs([
                a.link("contents", "Contents")
            ], "New contents"),
            a.form("New content", fields={
                "content_name": a.field("Content unique ID", "text", "primary", "non-empty"),
                "content_json": a.field("Content payload (any useful data)", "json", "primary", "non-empty")
            }, methods={
                "create": a.method("Create", "primary")
            }, data={"content_json": {}}),
            a.links("Navigate", [
                a.link("contents", "Go back")
            ])
        ]

    def access_scopes(self):
        return ["store_admin"]


class NewCurrencyController(a.AdminController):
    @coroutine
    def create(self, currency_name, currency_title, currency_format, currency_symbol, currency_label):

        currencies = self.application.currencies

        try:
            currency_id = yield currencies.new_currency(self.gamespace, currency_name, currency_title,
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
                a.link("currencies", "Go back")
            ])
        ]

    def access_scopes(self):
        return ["store_admin"]


class NewTierComponentController(a.AdminController):
    @coroutine
    def create_component(self, **args):
        tiers = self.application.tiers

        component_name = self.context.get("component")
        tier_id = self.context.get("tier_id")

        if not TierAdminComponents.has_component(component_name):
            raise a.ActionError("Component '{0}' is not supported.")

        component_admin = yield self.get_component(component_name, tier_id)
        component_admin.update(**args)
        component_data = component_admin.dump()

        try:
            yield tiers.new_tier_component(self.gamespace, tier_id, component_name, component_data)
        except StoreError as e:
            raise a.ActionError("Failed to create store component: " + e.message)

        raise a.Redirect(
            "tier",
            message="Component has been created",
            tier_id=tier_id)

    @coroutine
    def get(self, tier_id):
        stores = self.application.stores
        tiers = self.application.tiers

        try:
            tier = yield tiers.get_tier(self.gamespace, tier_id)
        except StoreNotFound:
            raise a.ActionError("No such tier")

        try:
            store = yield stores.get_store(self.gamespace, tier.store_id)
        except StoreNotFound:
            raise a.ActionError("No such store")

        try:
            existent_components = yield tiers.list_tier_components(self.gamespace, tier_id)
        except StoreError as e:
            raise a.ActionError("Failed to get tier components: " + e.message)
        else:
            existent_components = set(component.name for component in existent_components)

        new_components = set(TierAdminComponents.components())
        components = list(new_components - existent_components)

        raise Return({
            "components": {component: component for component in components},
            "store_name": store.name,
            "tier_name": tier.name
        })

    @coroutine
    def get_component(self, component, tier_id):
        try:
            component_instance = TierAdminComponents.component(component, self, tier_id)
        except KeyError:
            raise a.ActionError("No such tier component")

        yield component_instance.init()

        raise a.Return(component_instance)

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
                a.link("tier", "Go back", tier_id=tier_id),
            ])
        ])

        return result

    def access_scopes(self):
        return ["store_admin"]

    @coroutine
    def select(self, component):
        stores = self.application.stores
        tiers = self.application.tiers

        tier_id = self.context.get("tier_id")

        try:
            tier = yield tiers.get_tier(self.gamespace, tier_id)
        except StoreNotFound:
            raise a.ActionError("No such tier")

        try:
            store = yield stores.get_store(self.gamespace, tier.store_id)
        except StoreNotFound:
            raise a.ActionError("No such store")

        component = yield self.get_component(component, tier_id)

        raise Return({
            "store_name": store.name,
            "tier_name": tier.name,
            "component": component
        })


class NewStoreComponentController(a.AdminController):
    @coroutine
    def create_component(self, **args):
        stores = self.application.stores

        component_name = self.context.get("component")
        store_id = self.context.get("store_id")

        if not StoreAdminComponents.has_component(component_name):
            raise a.ActionError("Component '{0}' is not supported.")

        component_admin = yield self.get_component(component_name, store_id)
        component_admin.update(**args)
        component_data = component_admin.dump()

        try:
            yield stores.new_store_component(self.gamespace, store_id, component_name, component_data)
        except StoreError as e:
            raise a.ActionError("Failed to create store component: " + e.message)

        raise a.Redirect(
            "store_settings",
            message="New component has been created",
            store_id=store_id)

    @coroutine
    def get(self, store_id):

        stores = self.application.stores

        try:
            store = yield stores.get_store(self.gamespace, store_id)
        except StoreNotFound:
            raise a.ActionError("No such store")

        try:
            existent_components = yield stores.list_store_components(self.gamespace, store_id)
        except StoreError as e:
            raise a.ActionError("Failed to get store components: " + e.message)
        else:
            existent_components = set(component.name for component in existent_components)

        new_components = set(StoreAdminComponents.components())
        components = list(new_components - existent_components)

        raise Return({
            "components": {component: component for component in components},
            "store_name": store.name
        })

    @coroutine
    def get_component(self, component, store_id):
        try:
            component_instance = StoreAdminComponents.component(component, self, store_id)
        except KeyError:
            raise a.ActionError("No such store component")

        yield component_instance.init()

        raise a.Return(component_instance)

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
                a.link("store_settings", "Go back", store_id=store_id),
            ])
        ])

        return result

    def access_scopes(self):
        return ["store_admin"]

    @coroutine
    def select(self, component):

        stores = self.application.stores
        store_id = self.context.get("store_id")

        try:
            store = yield stores.get_store(self.gamespace, store_id)
        except StoreNotFound:
            raise a.ActionError("No such store")

        component = yield self.get_component(component, store_id)

        raise Return({
            "store_name": store.name,
            "component": component
        })


class NewStoreController(a.AdminController):
    @coroutine
    def create(self, store_name):
        stores = self.application.stores

        try:
            store_id = yield stores.new_store(self.gamespace, store_name)
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
                "store_name": a.field("Store unique ID", "text", "primary", "non-empty")
            }, methods={
                "create": a.method("Create", "primary")
            }, data=data),
            a.links("Navigate", [
                a.link("contents", "Go back")
            ])
        ]

    def access_scopes(self):
        return ["store_admin"]


class NewStoreItemController(a.AdminController):
    @coroutine
    def create(self, item_name, item_data, item_contents):
        items = self.application.items

        billing_method = self.context.get("billing_method")

        if not BillingMethods.has_method(billing_method):
            raise a.ActionError("No such billing method")

        try:
            item_data = ujson.loads(item_data)
            item_contents = ujson.loads(item_contents)
        except (KeyError, ValueError):
            raise a.ActionError("Corrupted JSON")

        store_id = self.context.get("store_id")
        category_id = self.context.get("category_id")

        try:
            item_id = yield items.new_item(self.gamespace, store_id, category_id, item_name, item_contents, item_data,
                                           billing_method, {})
        except StoreError as e:
            raise a.ActionError("Failed to create new item: " + e.args[0])

        raise a.Redirect(
            "item",
            message="New item has been created",
            item_id=item_id)

    @coroutine
    def get(self, store_id, category_id, billing_method):

        stores = self.application.stores
        categories = self.application.categories
        contents = self.application.contents

        if not BillingMethods.has_method(billing_method):
            raise a.ActionError("No such billing method")

        try:
            store = yield stores.get_store(self.gamespace, store_id)
        except StoreNotFound:
            raise a.ActionError("No such store")

        try:
            category = yield categories.get_category(self.gamespace, category_id)
        except CategoryNotFound:
            raise a.ActionError("No such category")

        content_items = yield contents.list_contents(self.gamespace)

        try:
            scheme = yield categories.get_common_scheme(self.gamespace)
        except CategoryNotFound:
            scheme = {}

        category_schema = category.scheme
        common.update(scheme, category_schema)

        raise a.Return({
            "category_name": category.name,
            "store_name": store.name,
            "scheme": scheme,
            "content_items": content_items,
            "item_contents": {}
        })

    def render(self, data):
        return [
            a.breadcrumbs([
                a.link("stores", "Stores"),
                a.link("store", data["store_name"], store_id=self.context.get("store_id"))
            ], "Add new item to store"),
            a.form("New item (of category '{0}')".format(data["category_name"]), fields={
                "item_name": a.field("Item unique name", "text", "primary", "non-empty"),
                "item_data": a.field(
                    "Item properties", "dorn", "primary",
                    schema=data["scheme"]
                ),
                "item_contents": a.field(
                    "Item contents (entities, delivered to the user for the purchase)", "kv", "primary",
                    values={item.name: item.name for item in data["content_items"]}
                )
            }, methods={
                "create": a.method("Create", "primary")
            }, data=data),
            a.links("Navigate", [
                a.link("contents", "Go back")
            ])
        ]

    def access_scopes(self):
        return ["store_admin"]


class NewStoreTierController(a.AdminController):
    @coroutine
    def create(self, tier_name, tier_product, tier_prices):

        tiers = self.application.tiers

        try:
            tier_prices = ujson.loads(tier_prices)
        except (KeyError, ValueError):
            raise a.ActionError("Corrupted JSON")

        store_id = self.context.get("store_id")

        try:
            tier_id = yield tiers.new_tier(self.gamespace, store_id, tier_name, tier_product, tier_prices)
        except StoreError as e:
            raise a.ActionError("Failed to create new tier: " + e.args[0])

        raise a.Redirect(
            "tier",
            message="New tier has been created",
            tier_id=tier_id)

    @coroutine
    def get(self, store_id):

        stores = self.application.stores
        currencies = self.application.currencies

        try:
            store = yield stores.get_store(self.gamespace, store_id)
        except StoreNotFound:
            raise a.ActionError("No such store")

        raise a.Return({
            "store_name": store.name,
            "currencies": (yield currencies.list_currencies(self.gamespace)),
            "tier_prices": {}
        })

    def render(self, data):
        return [
            a.breadcrumbs([
                a.link("stores", "Stores"),
                a.link("store", data["store_name"], store_id=self.context.get("store_id")),
                a.link("tiers", "Tiers", store_id=self.context.get("store_id"))
            ], "Add new tier to store"),
            a.form("New tier", fields={
                "tier_name": a.field("Tier unique name", "text", "primary", "non-empty"),
                "tier_product": a.field("Product ID", "text", "primary", "non-empty"),
                "tier_prices": a.field(
                    "Tier prices (in cents)", "kv", "primary",
                    values={curr.name: curr.title for curr in data["currencies"]}
                )
            }, methods={
                "create": a.method("Create", "primary")
            }, data=data),
            a.links("Navigate", [
                a.link("contents", "Go back"),
                a.link("currencies", "Edit currencies", icon="bitcoin")
            ])
        ]

    def access_scopes(self):
        return ["store_admin"]


class OfflineBillingMethodAdmin(BillingMethodAdmin):
    def __init__(self, action, store_id):
        super(OfflineBillingMethodAdmin, self).__init__(action, store_id, OfflineBillingMethod)
        self.items = []

    def get(self):
        return {
            "currency": self.method.currency,
            "amount": self.method.amount
        }

    @coroutine
    def init(self):
        self.items = yield self.action.application.contents.list_contents(self.action.gamespace)

    def render(self):
        return {
            "currency": a.field("Currency", "select", "primary", "non-empty", values={
                item.name: item.name for item in self.items
            }),
            "amount": a.field("Price (in currency)", "text", "primary", "number")
        }

    def update(self, currency, amount):
        self.method.currency = currency
        self.method.amount = amount


class RootAdminController(a.AdminController):
    def render(self, data):
        return [
            a.links("Store service", [
                a.link("contents", "Edit contents", icon="paper-plane"),
                a.link("stores", "Edit stores", icon="shopping-bag"),
                a.link("categories", "Edit categories", icon="list-alt"),
                a.link("currencies", "Edit currencies", icon="bitcoin"),
            ])
        ]

    def access_scopes(self):
        return ["store_admin"]


class StoreController(a.AdminController):
    @coroutine
    def get(self, store_id):

        stores = self.application.stores
        items = self.application.items

        try:
            store = yield stores.get_store(self.gamespace, store_id)
        except StoreNotFound:
            raise a.ActionError("No such store")

        items = yield items.list_items(self.gamespace, store_id)

        result = {
            "items": items,
            "store_name": store.name
        }

        raise a.Return(result)

    @coroutine
    def publish(self):
        stores = self.application.stores
        store_id = self.context.get("store_id")

        try:
            yield stores.get_store(self.gamespace, store_id)
        except StoreNotFound:
            raise a.ActionError("No such store")

        yield stores.publish_store(self.gamespace, store_id)

        raise a.Redirect(
            "store",
            message="Store has been published",
            store_id=store_id)

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
                    "id": "title",
                    "title": "Title"
                },
                {
                    "id": "category",
                    "title": "Category"
                },
                {
                    "id": "method",
                    "title": "Billing method"
                },
                {
                    "id": "actions",
                    "title": "Actions"
                }
            ], [
                {
                    "name": [a.link("item", item.name, icon="shopping-bag", item_id=item.item_id)],
                    "category": item.category.name,
                    "method": item.method,
                    "title": item.title("EN"),
                    "actions": [a.button("item", "Delete", "danger", _method="delete", item_id=item.item_id)]
                } for item in data["items"]], "default"),

            a.form("Publish store", fields={}, methods={
                "publish": a.method("Publish this store", "success")
            }, data=data),
            a.links("Navigate", [
                a.link("stores", "Go back"),
                a.link("tiers", "Edit tiers", icon="apple", store_id=self.context.get("store_id")),
                a.link("orders", "Orders", icon="money", store_id=self.context.get("store_id")),
                a.link("store_settings", "Store settings", icon="cog", store_id=self.context.get("store_id")),
                a.link("choose_category", "Add new item", icon="plus", store_id=self.context.get("store_id")),
            ])
        ]

    def access_scopes(self):
        return ["store_admin"]


class StoreItemController(a.AdminController):
    @coroutine
    def delete(self, **ignored):
        items = self.application.items

        item_id = self.context.get("item_id")

        try:
            item = yield items.get_item(self.gamespace, item_id)
        except ItemNotFound:
            raise a.ActionError("No such item")

        store_id = item.store_id

        try:
            yield items.delete_item(self.gamespace, item_id)
        except ItemError as e:
            raise a.ActionError("Failed to delete item: " + e.args[0])

        raise a.Redirect(
            "store",
            message="Item has been deleted",
            store_id=store_id)

    @coroutine
    def get(self, item_id):

        stores = self.application.stores
        items = self.application.items
        categories = self.application.categories
        contents = self.application.contents

        try:
            item = yield items.get_item(self.gamespace, item_id)
        except ItemNotFound:
            raise a.ActionError("No such item")

        store_id = item.store_id
        category_id = item.category

        try:
            store = yield stores.get_store(self.gamespace, store_id)
        except StoreNotFound:
            raise a.ActionError("No such store")

        try:
            category = yield categories.get_category(self.gamespace, category_id)
        except CategoryNotFound:
            raise a.ActionError("No such category")

        content_items = yield contents.list_contents(self.gamespace)

        try:
            scheme = yield categories.get_common_scheme(self.gamespace)
        except CategoryNotFound:
            scheme = {}

        category_schema = category.scheme
        common.update(scheme, category_schema)

        item_method = item.method

        item_method_data = item.method_data
        method_instance = yield self.get_method(item_method, store_id)
        method_instance.load(item_method_data)

        raise a.Return({
            "category_name": category.name,
            "store_name": store.name,
            "scheme": scheme,
            "item_name": item.name,
            "item_data": item.data,
            "item_contents": item.contents,
            "content_items": content_items,
            "billing_method": item_method,
            "store_id": store_id,
            "billing_fields": method_instance.render(),
            "billing_data": method_instance.get()
        })

    @coroutine
    def get_method(self, item_method, store_id):
        try:
            method_instance = BillingMethods.method(item_method, self, store_id)
        except KeyError:
            raise a.ActionError("No such billing method")

        yield method_instance.init()

        raise a.Return(method_instance)

    def render(self, data):

        return [
            a.breadcrumbs([
                a.link("stores", "Stores"),
                a.link("store", data["store_name"], store_id=data.get("store_id"))
            ], data["item_name"]),
            a.form("Store item (of category '{0}')".format(data["category_name"]), fields={
                "item_name": a.field("Item unique name", "text", "primary", "non-empty"),
                "item_data": a.field(
                    "Item properties", "dorn", "primary",
                    schema=data["scheme"]
                ),
                "item_contents": a.field(
                    "Item contents (entities, delivered to the user for the purchase)", "kv", "primary",
                    values={item.name: item.name for item in data["content_items"]}
                )
            }, methods={
                "update": a.method("Update", "primary"),
                "delete": a.method("Delete this item", "danger"),
            }, data=data),
            a.form("Billing '{0}' (source of the purchase)".format(data["billing_method"]),
                   fields=data["billing_fields"],
                   methods={"update_billing": a.method("Update", "primary")}, data=data["billing_data"]),
            a.links("Navigate", [
                a.link("store", "Go back", store_id=data.get("store_id"))
            ])
        ]

    # noinspection PyUnusedLocal
    def access_scopes(self):
        return ["store_admin"]

    @coroutine
    def update(self, item_name, item_data, item_contents):
        items = self.application.items

        try:
            item_data = ujson.loads(item_data)
            item_contents = ujson.loads(item_contents)
        except (KeyError, ValueError):
            raise a.ActionError("Corrupted JSON")

        item_id = self.context.get("item_id")

        try:
            yield items.update_item(self.gamespace, item_id, item_name, item_contents, item_data)
        except ItemError as e:
            raise a.ActionError("Failed to update item: " + e.args[0])

        raise a.Redirect(
            "item",
            message="Item has been updated",
            item_id=item_id)

    @coroutine
    def update_billing(self, **data):
        items = self.application.items

        item_id = self.context.get("item_id")

        try:
            item = yield items.get_item(self.gamespace, item_id)
        except ItemNotFound:
            raise a.ActionError("No such item")

        store_id = item.store_id
        item_method = item.method
        item_method_data = item.method_data

        method_instance = yield self.get_method(item_method, store_id)
        method_instance.load(item_method_data)
        method_instance.update(**data)
        billing_data = method_instance.dump()

        try:
            yield items.update_item_billing(self.gamespace, item_id, billing_data)
        except ItemError as e:
            raise a.ActionError("Failed to update item: " + e.args[0])

        raise a.Redirect(
            "item",
            message="Item has been updated",
            item_id=item_id)


class StoreTierController(a.AdminController):
    @coroutine
    def change_component(self, **args):
        tiers = self.application.tiers

        component_id = self.context.get("component_id")
        tier_id = self.context.get("tier_id")

        try:
            component = yield tiers.get_tier_component(self.gamespace, tier_id, component_id)
        except StoreComponentNotFound as e:
            raise a.ActionError("No such tier component")

        name = component.name

        if not TierAdminComponents.has_component(name):
            raise a.ActionError("Component '{0}' is not supported.")

        component_admin = yield self.get_component(name, tier_id)
        component_admin.update(**args)
        component_data = component_admin.dump()

        try:
            yield tiers.update_tier_component(self.gamespace, tier_id, component_id, component_data)
        except StoreError as e:
            raise a.ActionError("Failed to update tier component: " + e.message)

        raise a.Redirect(
            "tier",
            message="Component has been updated",
            tier_id=tier_id)

    @coroutine
    def delete(self, **ignore):

        tiers = self.application.tiers
        tier_id = self.context.get("tier_id")

        try:
            tier = yield tiers.get_tier(self.gamespace, tier_id)
        except TierNotFound:
            raise a.ActionError("Tier not found")

        store_id = tier.store_id

        try:
            yield tiers.delete_tier(self.gamespace, tier_id)
        except StoreError as e:
            raise a.ActionError("Failed to delete tier: " + e.args[0])

        raise a.Redirect(
            "tiers",
            message="Tier has been deleted",
            store_id=store_id)

    @coroutine
    def delete_component(self, **args):
        tiers = self.application.tiers

        component_id = self.context.get("component_id")
        tier_id = self.context.get("tier_id")

        try:
            yield tiers.delete_tier_component(self.gamespace, tier_id, component_id)
        except StoreError as e:
            raise a.ActionError("Failed to delete tier component: " + e.message)

        raise a.Redirect(
            "tier",
            message="Component has been deleted",
            tier_id=tier_id)

    @coroutine
    def get(self, tier_id):

        stores = self.application.stores
        currencies = self.application.currencies
        tiers = self.application.tiers

        try:
            tier = yield tiers.get_tier(self.gamespace, tier_id)
        except TierNotFound:
            raise a.ActionError("Tier not found")

        store_id = tier.store_id

        try:
            store = yield stores.get_store(self.gamespace, store_id)
        except StoreNotFound:
            raise a.ActionError("No such store")

        try:
            tier_components = yield tiers.list_tier_components(self.gamespace, tier_id)
        except StoreError as e:
            raise a.ActionError("Failed to get store components: " + e.message)

        components = {}

        for component in tier_components:
            if StoreAdminComponents.has_component(component.name):
                component_admin = yield self.get_component(component.name, tier_id)
                component_admin.load(component.data)
                components[component.component_id] = component_admin

        raise a.Return({
            "store_name": store.name,
            "store_id": store_id,
            "currencies": (yield currencies.list_currencies(self.gamespace)),
            "tier_prices": tier.prices,
            "tier_name": tier.name,
            "tier_product": tier.product,
            "components": components
        })

    @coroutine
    def get_component(self, component, tier_id):
        try:
            component_instance = TierAdminComponents.component(component, self, tier_id)
        except KeyError:
            raise a.ActionError("No such tier component")

        yield component_instance.init()

        raise a.Return(component_instance)

    def render(self, data):
        result = [
            a.breadcrumbs([
                a.link("stores", "Stores"),
                a.link("store", data["store_name"], store_id=data["store_id"]),
                a.link("tiers", "Tiers", store_id=data["store_id"])
            ], data["tier_name"]),
            a.form("Edit tier", fields={
                "tier_name": a.field("Tier unique name", "text", "primary", "non-empty"),
                "tier_product": a.field("Product ID", "text", "primary", "non-empty"),
                "tier_prices": a.field(
                    "Tier prices (in cents)", "kv", "primary",
                    values={curr.name: curr.title for curr in data["currencies"]}
                )
            }, methods={
                "update": a.method("Update tier", "primary"),
                "delete": a.method("Delete tier", "danger")
            }, data=data)
        ]

        for component_id, component in data["components"].iteritems():
            result.append(a.form(component.name, fields=component.render(), methods={
                "change_component": a.method("Update component", "primary"),
                "delete_component": a.method("Delete component", "danger")
            }, data=component.get(), icon="briefcase", component_id=component_id))

        result.extend([
            a.links("Navigate", [
                a.link("store", "Go back", store_id=data["store_id"]),
                a.link("currencies", "Edit currencies", icon="bitcoin"),
                a.link("new_tier_component", "New component", icon="briefcase",
                       tier_id=self.context.get("tier_id"))
            ])
        ])

        return result

    def access_scopes(self):
        return ["store_admin"]

    @coroutine
    def update(self, tier_name, tier_product, tier_prices):

        tiers = self.application.tiers
        tier_id = self.context.get("tier_id")

        try:
            tier_prices = ujson.loads(tier_prices)
        except (KeyError, ValueError):
            raise a.ActionError("Corrupted JSON")

        try:
            yield tiers.update_tier(self.gamespace, tier_id, tier_name, tier_product, tier_prices)
        except StoreError as e:
            raise a.ActionError("Failed to update tier: " + e.args[0])

        raise a.Redirect(
            "tier",
            message="Component has been updated",
            tier_id=tier_id)


class StoreTiersController(a.AdminController):
    @coroutine
    def get(self, store_id):

        stores = self.application.stores
        tiers = self.application.tiers

        try:
            store = yield stores.get_store(self.gamespace, store_id)
        except StoreNotFound:
            raise a.ActionError("No such store")

        tiers = yield tiers.list_tiers(self.gamespace, store_id)

        result = {
            "tiers": tiers,
            "store_name": store.name
        }

        raise a.Return(result)

    def render(self, data):
        return [
            a.breadcrumbs([
                a.link("stores", "Stores"),
                a.link("store", data["store_name"], store_id=self.context.get("store_id"))
            ], "Tiers"),
            a.content("Items", [
                {
                    "id": "edit",
                    "title": "Edit"
                },
                {
                    "id": "name",
                    "title": "Name"
                },
                {
                    "id": "product",
                    "title": "Product ID"
                },
                {
                    "id": "actions",
                    "title": "Actions"
                }
            ], [{"edit": [a.button("tier", "Edit", "default", _method="get", tier_id=tier.tier_id)],
                 "name": tier.name,
                 "product": tier.product,
                 "actions": [a.button("tier", "Delete", "danger", _method="delete", tier_id=tier.tier_id)]
                 } for tier in data["tiers"]
                ], "default"),
            a.links("Navigate", [
                a.link("store", "Go back", store_id=self.context.get("store_id")),
                a.link("currencies", "Edit currencies", icon="bitcoin"),
                a.link("new_tier", "Add new tier", icon="plus", store_id=self.context.get("store_id")),
            ])
        ]

    def access_scopes(self):
        return ["store_admin"]


class StoreSettingsController(a.AdminController):
    @coroutine
    def change_component(self, **args):
        stores = self.application.stores

        component_id = self.context.get("component_id")
        store_id = self.context.get("store_id")

        try:
            component = yield stores.get_store_component(self.gamespace, store_id, component_id)
        except StoreComponentNotFound as e:
            raise a.ActionError("No such store component")

        name = component.name

        if not StoreAdminComponents.has_component(name):
            raise a.ActionError("Component '{0}' is not supported.")

        component_admin = yield self.get_component(name, store_id)
        component_admin.update(**args)
        component_data = component_admin.dump()

        try:
            yield stores.update_store_component(self.gamespace, store_id, component_id, component_data)
        except StoreError as e:
            raise a.ActionError("Failed to update store component: " + e.message)

        raise a.Redirect(
            "store_settings",
            message="Component has been updated",
            store_id=store_id)

    @coroutine
    def delete(self, danger):
        store_id = self.context.get("store_id")
        stores = self.application.stores

        if danger != "confirm":
            raise a.Redirect("store_settings", store_id=store_id)

        try:
            yield stores.delete_store(self.gamespace, store_id)
        except StoreError as e:
            raise a.ActionError("Failed to delete store: " + e.args[0])

        raise a.Redirect("stores", message="Store has been deleted")

    @coroutine
    def delete_component(self, **args):
        stores = self.application.stores

        component_id = self.context.get("component_id")
        store_id = self.context.get("store_id")

        try:
            yield stores.delete_store_component(self.gamespace, store_id, component_id)
        except StoreError as e:
            raise a.ActionError("Failed to delete store component: " + e.message)

        raise a.Redirect(
            "store_settings",
            message="Component has been deleted",
            store_id=store_id)

    @coroutine
    def get(self, store_id):

        stores = self.application.stores

        try:
            store = yield stores.get_store(self.gamespace, store_id)
        except StoreNotFound:
            raise a.ActionError("No such store")

        try:
            store_components = yield stores.list_store_components(self.gamespace, store_id)
        except StoreError as e:
            raise a.ActionError("Failed to get store components: " + e.message)

        components = {}

        for component in store_components:
            if StoreAdminComponents.has_component(component.name):
                component_admin = yield self.get_component(component.name, store_id)
                component_admin.load(component.data)
                components[component.component_id] = component_admin

        result = {
            "store_name": store.name,
            "store_components": components
        }

        raise a.Return(result)

    @coroutine
    def get_component(self, component, store_id):
        try:
            component_instance = StoreAdminComponents.component(component, self, store_id)
        except KeyError:
            raise a.ActionError("No such store component")

        yield component_instance.init()

        raise a.Return(component_instance)

    def render(self, data):
        store_id = self.context.get("store_id")

        result = [
            a.breadcrumbs([
                a.link("stores", "Stores"),
                a.link("store", data["store_name"], store_id=store_id)
            ], "Settings")
        ]

        for component_id, component in data["store_components"].iteritems():
            result.append(a.form(component.name, fields=component.render(), methods={
                "change_component": a.method("Update component", "primary"),
                "delete_component": a.method("Delete component", "danger")
            }, data=component.get(), icon=component.icon(), component_id=component_id))

        result.extend([
            a.form("Store info", fields={
                "store_name": a.field("Store unique ID", "text", "primary", "non-empty")
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
                a.link("store", "Go back", store_id=store_id),
                a.link("new_store_component", "New component", icon="briefcase", store_id=store_id),
            ])
        ])

        return result

    def access_scopes(self):
        return ["store_admin"]

    @coroutine
    def update(self, store_name):

        store_id = self.context.get("store_id")
        stores = self.application.stores

        try:
            yield stores.update_store(self.gamespace, store_id, store_name)
        except StoreError as e:
            raise a.ActionError("Failed to update store: " + e.args[0])

        raise a.Redirect(
            "store_settings",
            message="Store settings have been updated",
            store_id=store_id)


class StoresController(a.AdminController):
    @coroutine
    def get(self):
        contents = self.application.stores
        stores = yield contents.list_stores(self.gamespace)

        result = {
            "stores": stores
        }

        raise a.Return(result)

    def render(self, data):
        return [
            a.breadcrumbs([], "Stores"),
            a.links("Stores", [
                a.link("store", item.name, icon="shopping-bag", store_id=item.store_id)
                for item in data["stores"]
                ]),
            a.links("Navigate", [
                a.link("index", "Go back"),
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
                    a.link("tier", order.tier.name, icon="apple", tier_id=order.tier.tier_id)
                ],
                "item": [
                    a.link("item", order.item.name, icon="shopping-bag", item_id=order.item.item_id)
                ],
                "component": [
                    a.link("store_settings", order.component.name, icon="cog", store_id=order.order.store_id)
                ],
                "account": order.order.account_id,
                "amount": order.order.amount,
                "total": str(order.order.total / 100) + " " + str(order.order.currency),
                "status": [
                    {
                        OrdersModel.STATUS_NEW: a.status("New", "info", "check"),
                        OrdersModel.STATUS_CREATED: a.status("Created", "info", "refresh fa-spin"),
                        OrdersModel.STATUS_SUCCEEDED: a.status("Succeeded", "success", "check"),
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
            }, methods={
                "filter": a.method("Filter", "primary")
            }, data=data, icon="filter"),
            a.links("Navigate", [
                a.link("store", "Go back", store_id=self.context.get("store_id"))
            ])
        ]

    def access_scopes(self):
        return ["store_admin"]

    @coroutine
    def filter(self, **args):

        store_id = self.context.get("store_id")
        page = self.context.get("page", 1)

        filters = {
            "page": page
        }

        filters.update({
            k: v for k, v in args.iteritems() if v
        })

        raise a.Redirect("orders", store_id=store_id, **filters)

    @coroutine
    def get(self,
            store_id,
            page=1,
            order_item=None,
            order_tier=None,
            order_account=None,
            order_status=None,
            order_currency=None):

        stores = self.application.stores
        items = self.application.items
        tiers = self.application.tiers
        currencies = self.application.currencies

        try:
            store = yield stores.get_store(self.gamespace, store_id)
        except StoreNotFound:
            raise a.ActionError("No such store")

        try:
            store_items = yield items.list_items(self.gamespace, store_id)
        except ItemError as e:
            raise a.ActionError("Failed to list store items: " + e.message)

        try:
            store_tiers = yield tiers.list_tiers(self.gamespace, store_id)
        except ItemError as e:
            raise a.ActionError("Failed to list store tiers: " + e.message)

        try:
            currencies_list = yield currencies.list_currencies(self.gamespace)
        except CurrencyError as e:
            raise a.ActionError("Failed to list currencies: " + e.message)

        page = common.to_int(page)

        orders = self.application.orders

        q = orders.orders_query(self.gamespace, store_id)

        q.offset = (page - 1) * OrdersController.ORDERS_PER_PAGE
        q.limit = OrdersController.ORDERS_PER_PAGE

        q.item = order_item
        q.tier = order_tier
        q.account = order_account
        q.status = order_status
        q.currency = order_currency

        orders, count = yield q.query(count=True)
        pages = int(math.ceil(float(count) / float(OrdersController.ORDERS_PER_PAGE)))

        store_items = {
            item.item_id: item.name
            for item in store_items
        }
        store_items[""] = "Any"

        store_tiers = {
            tier.tier_id: tier.name
            for tier in store_tiers
        }
        store_tiers[""] = "Any"

        currencies_list = {
            currency.name: currency.title
            for currency in currencies_list
        }
        currencies_list[""] = "Any"

        raise Return({
            "orders": orders,
            "pages": pages,
            "order_item": order_item,
            "order_tier": order_tier,
            "order_status": order_status,
            "order_account": order_account,
            "order_currency": order_currency,
            "store_name": store.name,
            "store_items": store_items,
            "store_tiers": store_tiers,
            "currencies_list": currencies_list,
            "order_statuses": {
                "": "Any",
                OrdersModel.STATUS_NEW: "New",
                OrdersModel.STATUS_SUCCEEDED: "Succeeded",
                OrdersModel.STATUS_ERROR: "Error",
                OrdersModel.STATUS_CREATED: "Created"
            }
        })


class BillingMethods(object):
    METHODS = {
        "offline": OfflineBillingMethodAdmin,
        "iap": IAPBillingMethodAdmin
    }

    @staticmethod
    def has_method(method_name):
        return method_name in BillingMethods.METHODS

    @staticmethod
    def method(method_name, action, store_id):
        return BillingMethods.METHODS[method_name](action, store_id)

    @staticmethod
    def methods():
        return BillingMethods.METHODS.keys()


def init():
    import appstore
    import steam
