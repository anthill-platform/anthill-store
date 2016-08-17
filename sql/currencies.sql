CREATE TABLE `currencies` (
  `currency_id` int(11) unsigned NOT NULL AUTO_INCREMENT,
  `gamespace_id` int(11) NOT NULL,
  `currency_name` varchar(255) NOT NULL DEFAULT '',
  `currency_title` varchar(255) NOT NULL DEFAULT '',
  `currency_format` varchar(255) NOT NULL DEFAULT '',
  `currency_symbol` varchar(8) NOT NULL DEFAULT '',
  `currency_label` varchar(64) NOT NULL DEFAULT '',
  PRIMARY KEY (`currency_id`),
  UNIQUE KEY `currency_name` (`currency_name`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8;