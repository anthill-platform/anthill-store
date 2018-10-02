CREATE TABLE `campaigns` (
  `campaign_id` int(11) unsigned NOT NULL AUTO_INCREMENT,
  `gamespace_id` int(11) unsigned NOT NULL,
  `store_id` int(11) unsigned NOT NULL,
  `campaign_name` varchar(255) NOT NULL DEFAULT '',
  `campaign_time_start` datetime NOT NULL,
  `campaign_time_end` datetime NOT NULL,
  `campaign_data` json NOT NULL,
  `campaign_enabled` tinyint(1) NOT NULL DEFAULT '1',
  PRIMARY KEY (`campaign_id`),
  KEY `store_id` (`store_id`),
  CONSTRAINT `campaigns_ibfk_1` FOREIGN KEY (`store_id`) REFERENCES `stores` (`store_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;