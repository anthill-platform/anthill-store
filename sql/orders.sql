CREATE TABLE `orders` (
  `order_id` int(11) unsigned NOT NULL AUTO_INCREMENT,
  `gamespace_id` int(11) unsigned NOT NULL,
  `store_id` int(11) unsigned NOT NULL,
  `pack_id` int(11) unsigned NOT NULL,
  `item_id` int(11) unsigned NOT NULL,
  `component_id` int(11) unsigned NOT NULL,
  `account_id` int(11) unsigned NOT NULL,
  `order_amount` int(11) unsigned NOT NULL,
  `order_status` enum('NEW','CREATED','SUCCEEDED','ERROR') NOT NULL DEFAULT 'NEW',
  `order_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `order_currency` varchar(16) NOT NULL DEFAULT '',
  `order_total` float NOT NULL,
  `order_info` json DEFAULT NULL,
  PRIMARY KEY (`order_id`),
  KEY `store_id` (`store_id`),
  KEY `pack_id` (`pack_id`),
  KEY `item_id` (`item_id`),
  CONSTRAINT `orders_ibfk_1` FOREIGN KEY (`store_id`) REFERENCES `stores` (`store_id`),
  CONSTRAINT `orders_ibfk_3` FOREIGN KEY (`pack_id`) REFERENCES `packs` (`pack_id`),
  CONSTRAINT `orders_ibfk_4` FOREIGN KEY (`item_id`) REFERENCES `items` (`item_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;