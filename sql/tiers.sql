CREATE TABLE `tiers` (
  `tier_id` int(11) unsigned NOT NULL AUTO_INCREMENT,
  `gamespace_id` int(11) NOT NULL,
  `store_id` int(11) unsigned NOT NULL,
  `tier_name` varchar(255) NOT NULL DEFAULT '',
  `tier_product` varchar(255) NOT NULL DEFAULT '',
  `tier_prices` json NOT NULL,
  PRIMARY KEY (`tier_id`),
  UNIQUE KEY `tier_name` (`tier_name`),
  KEY `store_id` (`store_id`),
  CONSTRAINT `tiers_ibfk_1` FOREIGN KEY (`store_id`) REFERENCES `stores` (`store_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;