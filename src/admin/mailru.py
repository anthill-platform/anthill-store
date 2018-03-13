
from admin import StoreAdminComponents, TierAdminComponents, StoreComponentAdmin, TierComponentAdmin
from model.components.mailru import MailRuStoreComponent

import common.admin as a


class MailRuStoreComponentAdmin(StoreComponentAdmin):
    def __init__(self, name, action, store_id):
        super(MailRuStoreComponentAdmin, self).__init__(name, action, store_id, MailRuStoreComponent)

    def get(self):
        return {
        }

    def icon(self):
        return "credit-card"

    def render(self):
        return {
        }

    def update(self, **fields):
        pass


StoreAdminComponents.register_component("mailru", MailRuStoreComponentAdmin)
