CREATE TABLE `discounts` (
  `discount_id` int(11) unsigned NOT NULL AUTO_INCREMENT,
  `gamespace_id` int(11) NOT NULL,
  `store_id` int(10) unsigned NOT NULL,
  `discount_time_start` datetime NOT NULL,
  `discount_time_end` datetime NOT NULL,
  `discount_payload` json NOT NULL,
  PRIMARY KEY (`discount_id`),
  KEY `store_id` (`store_id`),
  CONSTRAINT `discounts_ibfk_1` FOREIGN KEY (`store_id`) REFERENCES `stores` (`store_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;