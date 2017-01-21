CREATE TABLE `tier_components` (
  `component_id` int(11) unsigned NOT NULL AUTO_INCREMENT,
  `tier_id` int(11) unsigned NOT NULL,
  `gamespace_id` int(11) NOT NULL,
  `component` varchar(32) NOT NULL DEFAULT '',
  `component_data` json NOT NULL,
  PRIMARY KEY (`component_id`),
  KEY `tier_id` (`tier_id`),
  CONSTRAINT `tier_components_ibfk_1` FOREIGN KEY (`tier_id`) REFERENCES `tiers` (`tier_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;