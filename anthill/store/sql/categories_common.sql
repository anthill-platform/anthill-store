CREATE TABLE `categories_common` (
  `gamespace_id` int(11) NOT NULL,
  `public_item_scheme` json NOT NULL,
  `private_item_scheme` json NOT NULL,
  PRIMARY KEY (`gamespace_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;