CREATE TABLE `stores` (
  `store_id` int(11) unsigned NOT NULL AUTO_INCREMENT,
  `gamespace_id` int(11) NOT NULL,
  `store_name` varchar(255) DEFAULT NULL,
  `store_campaign_scheme` json DEFAULT NULL,
  PRIMARY KEY (`store_id`),
  UNIQUE KEY `gamespace_id` (`gamespace_id`,`store_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;