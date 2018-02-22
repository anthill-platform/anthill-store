CREATE TABLE `items` (
  `item_id` int(11) unsigned NOT NULL AUTO_INCREMENT,
  `gamespace_id` int(11) NOT NULL,
  `store_id` int(11) unsigned NOT NULL,
  `item_category` int(11) unsigned NOT NULL,
  `item_name` varchar(255) NOT NULL DEFAULT '',
  `item_public_data` json NOT NULL,
  `item_private_data` json NOT NULL,
  `item_tier` int(11) unsigned NOT NULL,
  `item_enabled` tinyint(1) NOT NULL DEFAULT '1',
  PRIMARY KEY (`item_id`),
  UNIQUE KEY `gamespace_id` (`gamespace_id`,`store_id`,`item_name`),
  KEY `item_category` (`item_category`),
  KEY `store_id` (`store_id`),
  KEY `item_tier` (`item_tier`),
  CONSTRAINT `items_ibfk_1` FOREIGN KEY (`item_category`) REFERENCES `categories` (`category_id`),
  CONSTRAINT `items_ibfk_2` FOREIGN KEY (`store_id`) REFERENCES `stores` (`store_id`),
  CONSTRAINT `items_ibfk_3` FOREIGN KEY (`item_tier`) REFERENCES `tiers` (`tier_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;