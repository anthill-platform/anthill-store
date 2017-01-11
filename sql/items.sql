CREATE TABLE `items` (
  `item_id` int(11) unsigned NOT NULL AUTO_INCREMENT,
  `gamespace_id` int(11) NOT NULL,
  `item_name` varchar(255) NOT NULL DEFAULT '',
  `item_json` json NOT NULL,
  `item_category` int(11) unsigned NOT NULL,
  `item_method` varchar(255) NOT NULL DEFAULT '',
  `item_method_data` json NOT NULL,
  `store_id` int(11) unsigned NOT NULL,
  `item_contents` json NOT NULL,
  PRIMARY KEY (`item_id`),
  UNIQUE KEY `item_name` (`item_name`),
  KEY `item_category` (`item_category`),
  KEY `store_id` (`store_id`),
  CONSTRAINT `items_ibfk_1` FOREIGN KEY (`item_category`) REFERENCES `categories` (`category_id`),
  CONSTRAINT `items_ibfk_2` FOREIGN KEY (`store_id`) REFERENCES `stores` (`store_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;