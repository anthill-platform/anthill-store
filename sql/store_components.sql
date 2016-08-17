CREATE TABLE `store_components` (
  `component_id` int(11) unsigned NOT NULL AUTO_INCREMENT,
  `store_id` int(11) NOT NULL,
  `gamespace_id` int(11) NOT NULL,
  `component` varchar(32) NOT NULL DEFAULT '',
  `component_data` json NOT NULL,
  PRIMARY KEY (`component_id`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8;