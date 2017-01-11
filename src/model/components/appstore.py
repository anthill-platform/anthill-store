
from tornado.gen import coroutine, Return

from . import StoreComponent, TierComponent, StoreComponents, TierComponents


class AppStoreStoreComponent(StoreComponent):

    LIVE_VERIFY_URL = "https://sandbox.itunes.apple.com/verifyReceipt"
    SANDBOX_VERIFY_URL = "https://buy.itunes.apple.com/verifyReceipt"

    def __init__(self):
        super(AppStoreStoreComponent, self).__init__()
        self.sandbox = False

    def dump(self):
        result = super(AppStoreStoreComponent, self).dump()
        result.update({
            "sandbox": self.sandbox
        })
        return result

    def load(self, data):
        super(AppStoreStoreComponent, self).load(data)
        self.sandbox = data.get("sandbox")


class AppStoreTierComponent(TierComponent):
    def __init__(self):
        super(AppStoreTierComponent, self).__init__()


StoreComponents.register_component("appstore", AppStoreStoreComponent)
TierComponents.register_component("appstore", AppStoreTierComponent)
