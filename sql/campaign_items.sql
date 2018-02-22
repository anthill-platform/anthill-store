CREATE TABLE `campaign_items` (
  `gamespace_id` int(11) unsigned NOT NULL,
  `campaign_id` int(11) unsigned NOT NULL,
  `item_id` int(11) unsigned NOT NULL,
  `campaign_item_private_data` json NOT NULL,
  `campaign_item_public_data` json NOT NULL,
  `campaign_item_tier` int(11) unsigned NOT NULL,
  UNIQUE KEY `gamespace_id` (`gamespace_id`,`campaign_id`,`item_id`),
  KEY `campaign_id` (`campaign_id`),
  KEY `item_id` (`item_id`),
  KEY `campaign_item_tier` (`campaign_item_tier`),
  CONSTRAINT `campaign_items_ibfk_1` FOREIGN KEY (`campaign_id`) REFERENCES `campaigns` (`campaign_id`) ON DELETE CASCADE,
  CONSTRAINT `campaign_items_ibfk_2` FOREIGN KEY (`item_id`) REFERENCES `items` (`item_id`) ON DELETE CASCADE,
  CONSTRAINT `campaign_items_ibfk_3` FOREIGN KEY (`campaign_item_tier`) REFERENCES `tiers` (`tier_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;