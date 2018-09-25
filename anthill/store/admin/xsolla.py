
from . import StoreAdminComponents, TierAdminComponents, StoreComponentAdmin, TierComponentAdmin
from .. model.components.xsolla import XsollaStoreComponent

import anthill.common.admin as a


class XsollaStoreComponentAdmin(StoreComponentAdmin):
    def __init__(self, name, action, store_id):
        super(XsollaStoreComponentAdmin, self).__init__(name, action, store_id, XsollaStoreComponent)

    def get(self):
        return {
            "sandbox": self.component.sandbox,
            "project_id": self.component.project_id,
        }

    def icon(self):
        return "credit-card"

    def render(self):
        return {
            "sandbox": a.field("Sandbox environment", "switch", "primary", "non-empty"),
            "project_id": a.field("Project ID", "text", "primary", "number")
        }

    def update(self, sandbox=False, project_id=0, **fields):
        self.component.sandbox = sandbox
        self.component.project_id = project_id


StoreAdminComponents.register_component("xsolla", XsollaStoreComponentAdmin)
