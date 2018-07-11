from steam import SteamStoreComponent
from . import StoreComponents


class MailRuStoreComponent(SteamStoreComponent):
    """
    MailRu store component copies SteamStoreComponent, except has different URLs
    """
    API_URL = "https://api.games.mail.ru/steam/ISteamMicroTxn"
    SANDBOX_API_URL = "https://api.games.mail.ru/steam/ISteamMicroTxnSandbox"
    INIT_TX_VERSION = "v3"
    UPDATE_TX_VERSION = "v2"

    def __init__(self):
        super(MailRuStoreComponent, self).__init__(
            api_url=MailRuStoreComponent.API_URL,
            sandbox_api_url=MailRuStoreComponent.SANDBOX_API_URL,
            init_tx_version=MailRuStoreComponent.INIT_TX_VERSION,
            update_tx_version=MailRuStoreComponent.UPDATE_TX_VERSION)

    def get_api(self, app):
        return app.mailru_api


StoreComponents.register_component("mailru", MailRuStoreComponent)
