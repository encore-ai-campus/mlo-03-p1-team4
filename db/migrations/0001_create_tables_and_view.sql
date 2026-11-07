-- 원본: spacecube.sql (2026-11-07 덤프). 데이터 없이 빈 테이블 12개와 뷰 1개 생성.
-- 기존 테이블이 있으면 CREATE TABLE 오류로 중단된다. DROP/DELETE/INSERT 없음.
-- 원본 덤프의 AUTO_INCREMENT 현재값은 제거하여 새 테이블에서 1부터 시작.
-- 실행: 빈 스키마를 만들고 선택한 다음 한 번만 실행한다.
--   mariadb -h <호스트> -u <관리자> -p spacecube < db/0001_create_tables_and_view.sql
--
-- 기준 db/migrations/0001_init.sql과의 차이 (원본 덤프의 CREATE 정의 기준):
-- 1. users: ck_users_email_at CHECK (email LIKE '%@%')가 추가되어 있다.
--    기준 0001_init.sql에는 이 제약이 없다. 기준 문서와 다른 부분이므로 확인이 필요하다.
-- 2. reservation_slots: KEY fk_slot_resv (reservation_id, venue_id, slot_date)가 명시되어 있다.
--    기준 0001_init.sql에는 이 KEY 선언이 없다.
-- 3. 덤프 표현 차이: 정수 표시 폭, BOOLEAN의 tinyint(1) 표기, NULL의 DEFAULT NULL 표기,
--    CHECK 식의 괄호·대소문자 등은 MariaDB가 내보낸 형태를 유지했다.

CREATE TABLE `regions` (
  `region_id` int(11) NOT NULL AUTO_INCREMENT,
  `sido` varchar(20) NOT NULL,
  `sigungu` varchar(30) NOT NULL,
  PRIMARY KEY (`region_id`),
  UNIQUE KEY `uq_regions` (`sido`,`sigungu`)
) ENGINE=InnoDB;

CREATE TABLE `categories` (
  `category_id` smallint(6) NOT NULL AUTO_INCREMENT,
  `code` varchar(20) NOT NULL,
  `name` varchar(20) NOT NULL,
  PRIMARY KEY (`category_id`),
  UNIQUE KEY `uq_categories_code` (`code`)
) ENGINE=InnoDB;

CREATE TABLE `facilities` (
  `facility_id` smallint(6) NOT NULL AUTO_INCREMENT,
  `name` varchar(30) NOT NULL,
  PRIMARY KEY (`facility_id`),
  UNIQUE KEY `uq_facilities_name` (`name`)
) ENGINE=InnoDB;

CREATE TABLE `users` (
  `user_id` bigint(20) NOT NULL AUTO_INCREMENT,
  `email` varchar(100) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `name` varchar(50) NOT NULL,
  `phone` varchar(20) DEFAULT NULL,
  `birth` char(6) NOT NULL,
  `gender_digit` char(1) NOT NULL,
  `marketing_agreed` tinyint(1) NOT NULL DEFAULT 0,
  `terms_agreed_at` datetime NOT NULL,
  `privacy_agreed_at` datetime NOT NULL,
  `is_synthetic` tinyint(1) NOT NULL DEFAULT 0,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `uq_users_email` (`email`),
  CONSTRAINT `ck_users_birth` CHECK (`birth` regexp '^[0-9]{6}$'),
  CONSTRAINT `ck_users_gender` CHECK (`gender_digit` in ('1','2','3','4')),
  CONSTRAINT `ck_users_email_at` CHECK (`email` like '%@%')
) ENGINE=InnoDB;

CREATE TABLE `venues` (
  `venue_id` bigint(20) NOT NULL AUTO_INCREMENT,
  `region_id` int(11) NOT NULL,
  `category_id` smallint(6) NOT NULL,
  `name` varchar(100) NOT NULL,
  `description` text DEFAULT NULL,
  `notice` text DEFAULT NULL,
  `capacity_max` smallint(6) NOT NULL,
  `price_per_hour` int(11) NOT NULL,
  `min_hours` tinyint(4) NOT NULL DEFAULT 1,
  `open_hour` tinyint(4) NOT NULL DEFAULT 9,
  `close_hour` tinyint(4) NOT NULL DEFAULT 23,
  `source_site` varchar(30) DEFAULT NULL,
  `source_id` varchar(50) DEFAULT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT 1,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`venue_id`),
  UNIQUE KEY `uq_venues_source` (`source_site`,`source_id`),
  KEY `ix_venues_category` (`category_id`,`is_active`),
  KEY `ix_venues_region` (`region_id`,`is_active`),
  KEY `ix_venues_created` (`created_at`),
  CONSTRAINT `fk_venues_category` FOREIGN KEY (`category_id`) REFERENCES `categories` (`category_id`),
  CONSTRAINT `fk_venues_region` FOREIGN KEY (`region_id`) REFERENCES `regions` (`region_id`),
  CONSTRAINT `ck_venues_capacity` CHECK (`capacity_max` >= 1),
  CONSTRAINT `ck_venues_price` CHECK (`price_per_hour` > 0),
  CONSTRAINT `ck_venues_hours` CHECK (`open_hour` between 9 and 22 and `close_hour` between 10 and 23 and `close_hour` > `open_hour`),
  CONSTRAINT `ck_venues_min` CHECK (`min_hours` between 1 and 4)
) ENGINE=InnoDB;

CREATE TABLE `venue_facilities` (
  `venue_id` bigint(20) NOT NULL,
  `facility_id` smallint(6) NOT NULL,
  PRIMARY KEY (`venue_id`,`facility_id`),
  KEY `ix_vf_facility` (`facility_id`,`venue_id`),
  CONSTRAINT `fk_vf_facility` FOREIGN KEY (`facility_id`) REFERENCES `facilities` (`facility_id`),
  CONSTRAINT `fk_vf_venue` FOREIGN KEY (`venue_id`) REFERENCES `venues` (`venue_id`) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE `venue_images` (
  `image_id` bigint(20) NOT NULL AUTO_INCREMENT,
  `venue_id` bigint(20) NOT NULL,
  `url` varchar(500) NOT NULL,
  `sort_order` tinyint(4) NOT NULL DEFAULT 0,
  PRIMARY KEY (`image_id`),
  KEY `ix_vi_venue` (`venue_id`,`sort_order`),
  CONSTRAINT `fk_vi_venue` FOREIGN KEY (`venue_id`) REFERENCES `venues` (`venue_id`) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE `reservations` (
  `reservation_id` bigint(20) NOT NULL AUTO_INCREMENT,
  `user_id` bigint(20) NOT NULL,
  `venue_id` bigint(20) NOT NULL,
  `reserve_date` date NOT NULL,
  `start_hour` tinyint(4) NOT NULL,
  `end_hour` tinyint(4) NOT NULL,
  `headcount` smallint(6) NOT NULL,
  `total_price` int(11) NOT NULL,
  `status` enum('confirmed','completed','cancelled') NOT NULL DEFAULT 'confirmed',
  `is_synthetic` tinyint(1) NOT NULL DEFAULT 0,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`reservation_id`),
  UNIQUE KEY `uq_resv_venue_date` (`reservation_id`,`venue_id`,`reserve_date`),
  KEY `ix_resv_user` (`user_id`,`status`,`reserve_date`),
  KEY `ix_resv_venue_date` (`venue_id`,`reserve_date`),
  KEY `ix_resv_status_date` (`status`,`reserve_date`),
  KEY `ix_resv_created` (`created_at`,`venue_id`),
  CONSTRAINT `fk_resv_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`),
  CONSTRAINT `fk_resv_venue` FOREIGN KEY (`venue_id`) REFERENCES `venues` (`venue_id`),
  CONSTRAINT `ck_resv_hours` CHECK (`start_hour` between 9 and 22 and `end_hour` <= 23 and `end_hour` > `start_hour` and `end_hour` - `start_hour` <= 4),
  CONSTRAINT `ck_resv_head` CHECK (`headcount` >= 1),
  CONSTRAINT `ck_resv_price` CHECK (`total_price` >= 0)
) ENGINE=InnoDB;

CREATE TABLE `reservation_slots` (
  `venue_id` bigint(20) NOT NULL,
  `slot_date` date NOT NULL,
  `slot_hour` tinyint(4) NOT NULL,
  `reservation_id` bigint(20) NOT NULL,
  PRIMARY KEY (`venue_id`,`slot_date`,`slot_hour`),
  UNIQUE KEY `uq_slot_resv` (`reservation_id`,`slot_hour`),
  KEY `fk_slot_resv` (`reservation_id`,`venue_id`,`slot_date`),
  CONSTRAINT `fk_slot_resv` FOREIGN KEY (`reservation_id`, `venue_id`, `slot_date`) REFERENCES `reservations` (`reservation_id`, `venue_id`, `reserve_date`) ON DELETE CASCADE,
  CONSTRAINT `ck_slot_hour` CHECK (`slot_hour` between 9 and 22)
) ENGINE=InnoDB;

CREATE TABLE `payments` (
  `payment_id` bigint(20) NOT NULL AUTO_INCREMENT,
  `reservation_id` bigint(20) NOT NULL,
  `method` enum('transfer','card','phone') NOT NULL,
  `status` enum('paid','refunded') NOT NULL DEFAULT 'paid',
  `paid_at` datetime NOT NULL DEFAULT current_timestamp(),
  `refunded_at` datetime DEFAULT NULL,
  PRIMARY KEY (`payment_id`),
  UNIQUE KEY `uq_pay_resv` (`reservation_id`),
  CONSTRAINT `fk_pay_resv` FOREIGN KEY (`reservation_id`) REFERENCES `reservations` (`reservation_id`),
  CONSTRAINT `ck_pay_refund` CHECK (`status` = 'refunded' = (`refunded_at` is not null))
) ENGINE=InnoDB;

CREATE TABLE `reviews` (
  `review_id` bigint(20) NOT NULL AUTO_INCREMENT,
  `reservation_id` bigint(20) NOT NULL,
  `user_id` bigint(20) NOT NULL,
  `rating` tinyint(4) NOT NULL,
  `content` text NOT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`review_id`),
  UNIQUE KEY `uq_review_resv` (`reservation_id`),
  KEY `ix_review_user` (`user_id`,`created_at`),
  KEY `ix_review_created` (`created_at`),
  CONSTRAINT `fk_review_resv` FOREIGN KEY (`reservation_id`) REFERENCES `reservations` (`reservation_id`),
  CONSTRAINT `fk_review_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`),
  CONSTRAINT `ck_review_rating` CHECK (`rating` between 1 and 5)
) ENGINE=InnoDB;

CREATE TABLE `crawl_jobs` (
  `job_id` bigint(20) NOT NULL AUTO_INCREMENT,
  `source_site` varchar(30) NOT NULL,
  `started_at` datetime NOT NULL,
  `finished_at` datetime DEFAULT NULL,
  `new_ids` int(11) NOT NULL DEFAULT 0,
  `fetched` int(11) NOT NULL DEFAULT 0,
  `registered` int(11) NOT NULL DEFAULT 0,
  `status` enum('running','done','failed') NOT NULL DEFAULT 'running',
  PRIMARY KEY (`job_id`),
  KEY `ix_crawl_started` (`source_site`,`started_at`)
) ENGINE=InnoDB;

CREATE OR REPLACE VIEW v_venue_rating AS
SELECT r.venue_id,
       ROUND(AVG(v.rating), 1) AS rating_avg,
       COUNT(*)                AS review_count
  FROM reviews v
  JOIN reservations r ON r.reservation_id = v.reservation_id
 WHERE v.deleted_at IS NULL
 GROUP BY r.venue_id;
