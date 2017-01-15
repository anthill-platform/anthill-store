CREATE TABLE `packs` (
  `pack_id` int(11) unsigned NOT NULL AUTO_INCREMENT,
  `gamespace_id` int(11) NOT NULL,
  `store_id` int(11) NOT NULL,
  `pack_name` varchar(255) NOT NULL DEFAULT '',
  `pack_product` varchar(255) NOT NULL DEFAULT '',
  `pack_prices` json NOT NULL,
  PRIMARY KEY (`pack_id`),
  UNIQUE KEY `pack_name` (`pack_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;