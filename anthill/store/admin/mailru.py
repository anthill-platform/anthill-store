
from . import StoreAdminComponents, TierAdminComponents, StoreComponentAdmin, TierComponentAdmin
from . steam import SteamStoreComponentAdmin
from .. model.components.mailru import MailRuStoreComponent

import anthill.common.admin as a


class MailRuStoreComponentAdmin(SteamStoreComponentAdmin):
    """
    MailRu store component copies SteamStoreComponent, except has different URLs
    """
    def __init__(self, name, action, store_id):
        super(MailRuStoreComponentAdmin, self).__init__(name, action, store_id,
                                                        component=MailRuStoreComponent)


StoreAdminComponents.register_component("mailru", MailRuStoreComponentAdmin)
