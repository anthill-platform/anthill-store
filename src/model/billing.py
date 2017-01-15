

class BillingMethod(object):
    def __init__(self):
        pass

    def dump(self):
        raise NotImplementedError()

    def load(self, data):
        raise NotImplementedError()


class IAPBillingMethod(BillingMethod):
    def __init__(self):
        super(IAPBillingMethod, self).__init__()
        self.tier = None

    def dump(self):
        return {
            "tier": self.tier
        }

    def load(self, data):
        self.tier = data.get("tier", None)


class OfflineBillingMethod(BillingMethod):
    def __init__(self):
        super(OfflineBillingMethod, self).__init__()
        self.currency = None
        self.amount = 0

    def dump(self):
        return {
            "currency": self.currency,
            "amount": self.amount
        }

    def load(self, data):
        self.currency = data.get("currency", None)
        self.amount = data.get("amount", 0)
