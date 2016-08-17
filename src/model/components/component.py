

class StoreComponent(object):
    def __init__(self):
        self.bundle = ""

    def dump(self):
        return {
            "bundle": self.bundle
        }


    def load(self, data):
        self.bundle = data.get("bundle", "")

class TierComponent(object):
    def __init__(self):
        self.product = None

    def dump(self):
        return {
            "product": self.product
        }

    def load(self, data):
        self.product = data.get("product", None)
