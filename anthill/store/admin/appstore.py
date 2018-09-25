
from . import StoreAdminComponents, TierAdminComponents, StoreComponentAdmin, TierComponentAdmin
from .. model.components.appstore import AppStoreStoreComponent, AppStoreTierComponent

import anthill.common.admin as a


class AppStoreStoreComponentAdmin(StoreComponentAdmin):
    def __init__(self, name, action, store_id):
        super(AppStoreStoreComponentAdmin, self).__init__(name, action, store_id, AppStoreStoreComponent)

    def get(self):
        result = super(AppStoreStoreComponentAdmin, self).get()
        result.update({
            "sandbox": self.component.sandbox
        })
        return result

    def icon(self):
        return "apple"

    def render(self):
        result = super(AppStoreStoreComponentAdmin, self).render()
        result.update({
            "sandbox": a.field("Sandbox environment", "switch", "primary", "non-empty")
        })
        return result

    def update(self, sandbox=False, **fields):
        super(AppStoreStoreComponentAdmin, self).update(**fields)
        self.component.sandbox = sandbox


class AppStoreTierComponentAdmin(TierComponentAdmin):
    def __init__(self, name, action, tier_id):
        super(AppStoreTierComponentAdmin, self).__init__(name, action, tier_id, AppStoreTierComponent)


StoreAdminComponents.register_component("appstore", AppStoreStoreComponentAdmin)
TierAdminComponents.register_component("appstore", AppStoreTierComponentAdmin)
