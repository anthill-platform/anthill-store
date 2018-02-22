from tornado.gen import coroutine, Return

from common.validate import validate
from common.model import Model
from common.database import DatabaseError, DuplicateError
from common.access import utc_time

from tier import TierAdapter
from item import StoreItemAdapter

import ujson
import datetime
import pytz


class CampaignError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message

    def __str__(self):
        return str(self.code) + ": " + self.message


class CampaignNotFound(Exception):
    pass


class CampaignItemNotFound(Exception):
    pass


class CampaignAdapter(object):
    def __init__(self, data):
        self.campaign_id = str(data.get("campaign_id"))
        self.store_id = str(data.get("store_id"))
        self.name = str(data.get("campaign_name"))
        self.time_start = data.get("campaign_time_start")
        self.time_end = data.get("campaign_time_end")
        self.data = data.get("campaign_data")
        self.enabled = bool(data.get("campaign_enabled"))


class CampaignItemAdapter(object):
    def __init__(self, data):
        self.campaign_id = data.get("campaign_id")
        self.private_data = data.get("campaign_item_private_data")
        self.public_data = data.get("campaign_item_public_data")
        self.tier = str(data.get("campaign_item_tier"))


class CampaignTierStoreItemAdapter(object):
    def __init__(self, data):
        self.campaign_item = CampaignItemAdapter(data)
        self.item = StoreItemAdapter(data)
        self.tier = TierAdapter(data)
        self.campaign_tier_name = data.get("campaign_tier_name")
        self.campaign_tier_title = data.get("campaign_tier_title")
        self.campaign_tier_id = data.get("campaign_tier_id")


class CampaignItemCampaignAdapter(object):
    def __init__(self, data):
        self.campaign_item = CampaignItemAdapter(data)
        self.campaign = CampaignAdapter(data)
        self.tier = TierAdapter(data)
        self.item_id = str(data.get("item_id"))
        self.item_name = str(data.get("item_name"))


class CampaignItemTierAdapter(object):
    def __init__(self, data):
        self.campaign_item = CampaignItemAdapter(data)
        self.tier = TierAdapter(data)


class CampaignsModel(Model):
    def __init__(self, db):
        self.db = db

    def get_setup_db(self):
        return self.db

    def get_setup_tables(self):
        return ["campaigns", "campaign_items"]

    @coroutine
    @validate(gamespace_id="int", store_id="int", campaign_name="str",
              campaign_time_start="datetime", campaign_time_end="datetime",
              campaign_data="json_dict", campaign_enabled="bool")
    def new_campaign(self, gamespace_id, store_id, campaign_name, campaign_time_start, campaign_time_end,
                     campaign_data, campaign_enabled):
        try:
            campaign_id = yield self.db.insert(
                """
                INSERT INTO `campaigns`
                (`gamespace_id`, `store_id`, `campaign_name`, `campaign_time_start`, 
                 `campaign_time_end`, `campaign_data`, `campaign_enabled`) 
                VALUES (%s, %s, %s, %s, %s, %s, %s);
                """, gamespace_id, store_id, campaign_name, campaign_time_start,
                campaign_time_end, ujson.dumps(campaign_data), int(campaign_enabled)
            )
        except DatabaseError as e:
            raise CampaignError(500, "Failed to create a campaign: " + e.args[1])
        else:
            raise Return(campaign_id)

    @coroutine
    @validate(gamespace_id="int", campaign_id="int", campaign_name="str",
              campaign_time_start="datetime", campaign_time_end="datetime",
              campaign_data="json_dict", campaign_enabled="bool")
    def update_campaign(self, gamespace_id, campaign_id, campaign_name, campaign_time_start,
                        campaign_time_end, campaign_data, campaign_enabled):
        try:
            updated = yield self.db.execute(
                """
                UPDATE `campaigns`
                SET `campaign_name`=%s, `campaign_time_start`=%s, 
                    `campaign_time_end`=%s, `campaign_data`=%s, `campaign_enabled`=%s
                WHERE `gamespace_id`=%s AND `campaign_id`=%s
                LIMIT 1;
                """, campaign_name, campaign_time_start, campaign_time_end,
                ujson.dumps(campaign_data), int(campaign_enabled), gamespace_id, campaign_id,
            )
        except DatabaseError as e:
            raise CampaignError(500, "Failed to update a campaign: " + e.args[1])
        else:
            raise Return(updated)

    @coroutine
    @validate(gamespace_id="int", campaign_id="int")
    def delete_campaign(self, gamespace_id, campaign_id):
        try:
            deleted = yield self.db.execute(
                """
                DELETE FROM `campaigns`
                WHERE `gamespace_id`=%s AND `campaign_id`=%s
                LIMIT 1;
                """, gamespace_id, campaign_id
            )
        except DatabaseError as e:
            raise CampaignError(500, "Failed to delete a campaign: " + e.args[1])
        else:
            raise Return(deleted)

    @coroutine
    @validate(gamespace_id="int", store_id="int", offset="int", limit="int")
    def list_campaigns_count(self, gamespace_id, store_id, offset=0, limit=0):
        try:
            with (yield self.db.acquire()) as db:
                campaigns = yield db.query(
                    """
                    SELECT SQL_CALC_FOUND_ROWS * 
                    FROM `campaigns`
                    WHERE `gamespace_id`=%s AND `store_id`=%s
                    ORDER BY `campaign_id` DESC
                    LIMIT %s, %s;
                    """, gamespace_id, store_id, offset, limit)

                count_result = yield db.get(
                    """
                        SELECT FOUND_ROWS() AS count;
                    """)
                count_result = count_result["count"]

        except DatabaseError as e:
            raise CampaignError(500, "Failed to list campaigns: " + e.args[1])
        else:
            raise Return((map(CampaignAdapter, campaigns), count_result, ))

    @coroutine
    @validate(gamespace_id="int", campaign_id="int")
    def get_campaign(self, gamespace_id, campaign_id, db=None):
        try:
            campaign = yield (db or self.db).get(
                """
                SELECT * 
                FROM `campaigns`
                WHERE `gamespace_id`=%s AND `campaign_id`=%s
                LIMIT 1;
                """, gamespace_id, campaign_id
            )
        except DatabaseError as e:
            raise CampaignError(500, "Failed to get a campaign: " + e.args[1])
        else:
            if campaign is None:
                raise CampaignNotFound()

            raise Return(CampaignAdapter(campaign))

    @coroutine
    @validate(gamespace_id="int", campaign_id="int", item_id="int", campaign_item_private_data="json_dict",
              campaign_item_public_data="json_dict", campaign_item_tier="int")
    def add_campaign_item(self, gamespace_id, campaign_id, item_id, campaign_item_private_data,
                          campaign_item_public_data, campaign_item_tier):
        try:
            yield self.db.insert(
                """
                INSERT INTO `campaign_items`
                (`gamespace_id`, `campaign_id`, `item_id`, `campaign_item_private_data`, 
                 `campaign_item_public_data`, `campaign_item_tier`)
                VALUES (%s, %s, %s, %s, %s, %s);
                """, gamespace_id, campaign_id, item_id, ujson.dumps(campaign_item_private_data),
                ujson.dumps(campaign_item_public_data), campaign_item_tier
            )
        except DuplicateError:
            raise CampaignError(406, "This campaign alread has this item")
        except DatabaseError as e:
            raise CampaignError(500, "Failed to add item into campaign: " + e.args[1])

    @coroutine
    @validate(gamespace_id="int", campaign_id="int", item_id="int", campaign_item_private_data="json_dict",
              campaign_item_public_data="json_dict", campaign_item_tier="int")
    def update_campaign_item(self, gamespace_id, campaign_id, item_id,
                             campaign_item_private_data, campaign_item_public_data, campaign_item_tier):
        try:
            updated = yield self.db.execute(
                """
                UPDATE `campaign_items`
                SET `campaign_item_private_data`=%s, `campaign_item_public_data`=%s, `campaign_item_tier`=%s
                WHERE `gamespace_id`=%s AND `campaign_id`=%s AND `item_id`=%s
                LIMIT 1;
                """, ujson.dumps(campaign_item_private_data),
                ujson.dumps(campaign_item_public_data), campaign_item_tier,
                gamespace_id, campaign_id, item_id,
            )
        except DatabaseError as e:
            raise CampaignError(500, "Failed to update item in campaign: " + e.args[1])
        else:
            raise Return(updated)

    @coroutine
    @validate(gamespace_id="int", campaign_id="int", item_id="int")
    def delete_campaign_item(self, gamespace_id, campaign_id, item_id):
        try:
            deleted = yield self.db.execute(
                """
                DELETE FROM `campaign_items`
                WHERE `gamespace_id`=%s AND `campaign_id`=%s AND `item_id`=%s
                LIMIT 1;
                """, gamespace_id, campaign_id, item_id
            )
        except DatabaseError as e:
            raise CampaignError(500, "Failed to delete a campaign item: " + e.args[1])
        else:
            raise Return(deleted)

    @coroutine
    @validate(gamespace_id="int", campaign_id="int")
    def list_campaign_items(self, gamespace_id, campaign_id):
        try:
            campaign_items = yield self.db.query(
                """
                SELECT 
                    `campaign_items`.`campaign_item_private_data`,
                    `campaign_items`.`campaign_item_public_data`,
                    `campaign_items`.`campaign_item_tier`,
                    `items`.`item_id`,
                    `items`.`item_category`,
                    `items`.`item_name`,
                    `items`.`item_private_data`,
                    `items`.`item_public_data`,
                    `tiers`.`tier_id`,
                    `tiers`.`tier_title`,
                    `tiers`.`tier_name`,
                    `campaign_tiers`.`tier_title` AS `campaign_tier_title`,
                    `campaign_tiers`.`tier_name` AS `campaign_tier_name`,
                    `campaign_tiers`.`tier_id` AS `campaign_tier_id`
                FROM `campaign_items`, `items`, `tiers`, `tiers` AS `campaign_tiers`
                WHERE 
                    `campaign_items`.`gamespace_id`=%s AND 
                    `campaign_items`.`campaign_id`=%s AND
                    `campaign_items`.`item_id`=`items`.`item_id` AND
                    `tiers`.`tier_id`=`items`.`item_tier` AND
                    `campaign_items`.`campaign_item_tier`=`campaign_tiers`.`tier_id`
                ORDER BY `campaign_items`.`item_id` ASC;
                """, gamespace_id, campaign_id
            )
        except DatabaseError as e:
            raise CampaignError(500, "Failed to list campaign items: " + e.args[1])
        else:
            raise Return(map(CampaignTierStoreItemAdapter, campaign_items))

    @coroutine
    @validate(gamespace_id="int", store_id="int", item_id="int")
    def find_current_campaign_item(self, gamespace_id, store_id, item_id, db=None):
        try:
            dt = datetime.datetime.fromtimestamp(utc_time(), tz=pytz.utc).strftime('%Y-%m-%d %H:%M:%S')

            campaign_item = yield (db or self.db).get(
                """
                SELECT 
                    `campaign_items`.`campaign_item_public_data`,
                    `campaign_items`.`campaign_item_private_data`,
                    `campaigns`.`campaign_id`,
                    `tiers`.`tier_id`,
                    `tiers`.`tier_name`,
                    `tiers`.`tier_title`,
                    `tiers`.`tier_prices`,
                    `tiers`.`tier_product`
                FROM 
                    `campaign_items`, 
                    `campaigns`,
                    `tiers`
                WHERE 
                `campaigns`.`gamespace_id`=%s AND
                `campaigns`.`campaign_enabled`=1 AND
                `campaigns`.`store_id`=%s AND
                (%s BETWEEN `campaigns`.`campaign_time_start` AND `campaigns`.`campaign_time_end`) AND
                `campaign_items`.`item_id`=%s AND
                `campaign_items`.`campaign_id` = `campaigns`.`campaign_id` AND
                `campaign_items`.`campaign_item_tier` = `tiers`.`tier_id`
                ORDER BY `campaigns`.`campaign_time_start` ASC
                LIMIT 1;
                """, gamespace_id, store_id, dt, item_id
            )
        except DatabaseError as e:
            raise CampaignError(500, "Failed to list campaign items: " + e.args[1])
        else:
            if campaign_item is None:
                raise Return(None)
            raise Return(CampaignItemTierAdapter(campaign_item))

    @coroutine
    @validate(gamespace_id="int", store_id="int", extra_start_time="int", extra_end_time="int")
    def list_store_campaign_items(self, gamespace_id, store_id, extra_start_time=0, extra_end_time=0):
        try:
            dt = datetime.datetime.fromtimestamp(utc_time(), tz=pytz.utc).strftime('%Y-%m-%d %H:%M:%S')

            campaign_items = yield self.db.query(
                """
                SELECT 
                    `campaign_items`.`campaign_item_private_data`,
                    `campaign_items`.`campaign_item_public_data`,
                    `campaign_items`.`campaign_item_tier`,
                    `campaigns`.`campaign_id`,
                    `campaigns`.`campaign_data`,
                    `campaigns`.`campaign_time_start`,
                    `campaigns`.`campaign_time_end`,
                    `items`.`item_id`,
                    `items`.`item_name`,
                    `tiers`.`tier_id`,
                    `tiers`.`tier_name`,
                    `tiers`.`tier_title`,
                    `tiers`.`tier_product`,
                    `tiers`.`tier_prices`
                FROM 
                    `campaigns`, 
                    `campaign_items`, 
                    `items`, 
                    `tiers`
                WHERE 
                `campaigns`.`gamespace_id`=%s AND
                `campaigns`.`campaign_enabled`=1 AND
                `campaigns`.`store_id`=%s AND
                (%s BETWEEN DATE_SUB(`campaigns`.`campaign_time_start`, INTERVAL %s second) 
                        AND DATE_ADD(`campaigns`.`campaign_time_end`, INTERVAL %s second)) AND
                `campaign_items`.`campaign_id` = `campaigns`.`campaign_id` AND
                `campaign_items`.`campaign_item_tier` = `tiers`.`tier_id` AND
                `campaign_items`.`item_id`=`items`.`item_id` AND
                `items`.`item_enabled`=1;
                """, gamespace_id, store_id, dt, extra_start_time, extra_end_time
            )
        except DatabaseError as e:
            raise CampaignError(500, "Failed to list campaign items: " + e.args[1])
        else:
            raise Return(map(CampaignItemCampaignAdapter, campaign_items))

    @coroutine
    @validate(gamespace_id="int", campaign_id="int", item_id="int")
    def get_campaign_item(self, gamespace_id, campaign_id, item_id, db=None):
        try:
            campaign_item = yield (db or self.db).get(
                """
                SELECT * 
                FROM `campaign_items`
                WHERE `gamespace_id`=%s AND `campaign_id`=%s AND `item_id`=%s
                LIMIT 1;
                """, gamespace_id, campaign_id, item_id
            )
        except DatabaseError as e:
            raise CampaignError(500, "Failed to get a campaign item: " + e.args[1])
        else:
            if campaign_item is None:
                raise CampaignItemNotFound()

            raise Return(CampaignItemAdapter(campaign_item))

    @coroutine
    @validate(gamespace_id="int", clone_id_from="int", clone_id_to="int")
    def clone_campaign_items(self, gamespace_id, clone_id_from, clone_id_to, db=None):
        try:
            yield (db or self.db).get(
                """
                INSERT INTO `campaign_items`
                (`gamespace_id`, `campaign_id`, `item_id`, `campaign_item_private_data`, 
                  `campaign_item_public_data`, `campaign_item_tier`) 
                SELECT `gamespace_id`, %s, `item_id`, `campaign_item_private_data`, 
                  `campaign_item_public_data`, `campaign_item_tier`
                FROM `campaign_items`
                WHERE `gamespace_id`=%s AND `campaign_id`=%s;
                """, clone_id_to, gamespace_id, clone_id_from
            )
        except DatabaseError as e:
            raise CampaignError(500, "Failed to clone campaign items: " + e.args[1])
