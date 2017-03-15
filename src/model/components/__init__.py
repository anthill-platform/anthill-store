
from tornado.gen import coroutine


class NoSuchStoreComponentError(Exception):
    pass


class StoreComponentError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message

    def __str__(self):
        return self.message


class StoreComponent(object):
    def __init__(self):
        self.bundle = ""

    def dump(self):
        return {
            "bundle": self.bundle
        }

    def load(self, data):
        self.bundle = data.get("bundle", "")

    @coroutine
    def new_order(self, app, gamespace_id, account_id, order_id, currency, price, amount, total, store, item, env):
        raise NotImplementedError()


class TierComponent(object):
    def __init__(self):
        self.product = None

    def dump(self):
        return {
            "product": self.product
        }

    def load(self, data):
        self.product = data.get("product", None)


class StoreComponents(object):
    COMPONENTS = {}

    @staticmethod
    def component(component_name, data):

        try:
            cmp_class = StoreComponents.COMPONENTS[component_name]
        except KeyError:
            raise NoSuchStoreComponentError()

        instance = cmp_class()
        instance.load(data)
        return instance

    @staticmethod
    def components():
        return StoreComponents.COMPONENTS.keys()

    @staticmethod
    def has_component(component_name):
        return component_name in StoreComponents.COMPONENTS

    @staticmethod
    def register_component(component_name, component):
        StoreComponents.COMPONENTS[component_name] = component


class TierComponents(object):
    COMPONENTS = {}

    @staticmethod
    def component(component_name):
        return TierComponents.COMPONENTS[component_name](component_name)

    @staticmethod
    def components():
        return TierComponents.COMPONENTS.keys()

    @staticmethod
    def has_component(component_name):
        return component_name in TierComponents.COMPONENTS

    @staticmethod
    def register_component(component_name, component):
        TierComponents.COMPONENTS[component_name] = component
