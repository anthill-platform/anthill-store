
from common.model import Model


class DiscountsModel(Model):

    DEFAULT_SCHEME = {
        "type": "object",
        "options": {
            "disable_edit_json": True,
            "disable_properties": True
        },
        "properties": {}
    }

    def __init__(self, db):
        self.db = db

    def get_setup_db(self):
        return self.db

    def get_setup_tables(self):
        return ["discounts"]
