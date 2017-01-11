
from admin import StoreAdminComponents, TierAdminComponents, StoreComponentAdmin, TierComponentAdmin
from model.components.steam import SteamStoreComponent

import common.admin as a


class SteamStoreComponentAdmin(StoreComponentAdmin):
    def __init__(self, name, action, store_id):
        super(SteamStoreComponentAdmin, self).__init__(name, action, store_id, SteamStoreComponent)

    def get(self):
        return {
            "sandbox": self.component.sandbox,
            "app_id": self.component.app_id
        }

    def icon(self):
        return "steam"

    def render(self):
        return {
            "sandbox": a.field("Sandbox environment", "switch", "primary", "non-empty"),
            "app_id": a.field("Application ID", "text", "primary", "non-empty")
        }

    def update(self, app_id, sandbox=False, **fields):
        self.component.sandbox = sandbox
        self.component.app_id = app_id


StoreAdminComponents.register_component("steam", SteamStoreComponentAdmin)
