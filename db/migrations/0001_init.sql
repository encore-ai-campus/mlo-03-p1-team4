-- 0001_init — 공간큐브 MariaDB 첫 스키마 (2026-11-04)
-- 출처: docs/db/spacecube_mariadb.sql(11-03 수정안)을 그대로 옮김. 기준 문서: docs/산출물_04_DB명세서.md
-- 검증: 11-04 로컬 MariaDB 11.8에서 표 12·뷰 1·CHECK 12, 제약 시험 29건 통과(db/tests/check_ddl.py,
--       기록 docs/기록/검증_2026-11-04_DDL실행.md). RDS 11.4에서 같은 스크립트로 한 번 더 확인한다.
--
-- 실행: 빈 스키마를 먼저 만들고 그 스키마를 골라 한 번만 돌린다(다시 돌리면 CREATE TABLE에서 멈춤).
--   CREATE DATABASE spacecube CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
--   mariadb -h <호스트> -u <관리자> -p spacecube < db/migrations/0001_init.sql
-- 필수 설정: sql_mode에 STRICT_TRANS_TABLES, time_zone = Asia/Seoul(+09:00). 엔진 InnoDB, utf8mb4.
-- 이 파일은 적용된 뒤 고치지 않는다. 바꿀 것은 0002_… 새 파일로 만든다(db/migrations/README.md).

-- ───────── 기준 정보 ─────────

CREATE TABLE regions (
  region_id INT         NOT NULL AUTO_INCREMENT,
  sido      VARCHAR(20) NOT NULL,                 -- 서울, 경기 …
  sigungu   VARCHAR(30) NOT NULL,                 -- 관악구, 안성시 …
  PRIMARY KEY (region_id),
  UNIQUE KEY uq_regions (sido, sigungu)
) ENGINE=InnoDB;

CREATE TABLE categories (
  category_id SMALLINT    NOT NULL AUTO_INCREMENT,
  code        VARCHAR(20) NOT NULL,               -- studyroom, studio, cafe, lectureroom, partyroom (11-03 A3)
  name        VARCHAR(20) NOT NULL,
  PRIMARY KEY (category_id),
  UNIQUE KEY uq_categories_code (code)
) ENGINE=InnoDB;

CREATE TABLE facilities (
  facility_id SMALLINT    NOT NULL AUTO_INCREMENT,
  name        VARCHAR(30) NOT NULL,               -- 와이파이, 빔프로젝터 …
  PRIMARY KEY (facility_id),
  UNIQUE KEY uq_facilities_name (name)
) ENGINE=InnoDB;

-- ───────── 회원 ─────────

CREATE TABLE users (
  user_id          BIGINT       NOT NULL AUTO_INCREMENT,
  email            VARCHAR(100) NOT NULL,
  password_hash    VARCHAR(255) NOT NULL,         -- bcrypt
  name             VARCHAR(50)  NOT NULL,
  phone            VARCHAR(20)  NULL,
  birth            CHAR(6)      NOT NULL,         -- YYMMDD
  gender_digit     CHAR(1)      NOT NULL,         -- 1~4
  marketing_agreed BOOLEAN      NOT NULL DEFAULT FALSE,
  terms_agreed_at   DATETIME    NOT NULL,          -- 이용약관 필수 동의 시각 (11-03 A2)
  privacy_agreed_at DATETIME    NOT NULL,          -- 개인정보 수집·이용 필수 동의 시각 (11-03 A2)
  is_synthetic     BOOLEAN      NOT NULL DEFAULT FALSE,
  created_at       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at       DATETIME     NULL,
  PRIMARY KEY (user_id),
  UNIQUE KEY uq_users_email (email),
  CONSTRAINT ck_users_birth  CHECK (birth REGEXP '^[0-9]{6}$'),
  CONSTRAINT ck_users_gender CHECK (gender_digit IN ('1','2','3','4'))
) ENGINE=InnoDB;

-- ───────── 공간 (예약 단위) ─────────

CREATE TABLE venues (
  venue_id       BIGINT       NOT NULL AUTO_INCREMENT,
  region_id      INT          NOT NULL,
  category_id    SMALLINT     NOT NULL,
  name           VARCHAR(100) NOT NULL,           -- 생성 이름(시·군·구 + 유형 + 번호). 업체 실명 아님
  description    TEXT         NULL,               -- 유형별 템플릿
  notice         TEXT         NULL,               -- 이용 안내
  capacity_max   SMALLINT     NOT NULL,
  price_per_hour INT          NOT NULL,
  min_hours      TINYINT      NOT NULL DEFAULT 1, -- 복원: 크롤링 최소 예약시간 (명세서 2-3)
  open_hour      TINYINT      NOT NULL DEFAULT 9,
  close_hour     TINYINT      NOT NULL DEFAULT 23,
  source_site    VARCHAR(30)  NULL,               -- spacecloud, synthetic
  source_id      VARCHAR(50)  NULL,
  is_active      BOOLEAN      NOT NULL DEFAULT TRUE,
  created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,  -- NEW 14일 계산 기준
  PRIMARY KEY (venue_id),
  UNIQUE KEY uq_venues_source (source_site, source_id),
  KEY ix_venues_category (category_id, is_active),
  KEY ix_venues_region (region_id, is_active),
  KEY ix_venues_created (created_at),
  CONSTRAINT fk_venues_region   FOREIGN KEY (region_id)   REFERENCES regions (region_id),
  CONSTRAINT fk_venues_category FOREIGN KEY (category_id) REFERENCES categories (category_id),
  CONSTRAINT ck_venues_capacity CHECK (capacity_max >= 1),
  CONSTRAINT ck_venues_price    CHECK (price_per_hour > 0),
  CONSTRAINT ck_venues_hours    CHECK (open_hour BETWEEN 9 AND 22 AND close_hour BETWEEN 10 AND 23 AND close_hour > open_hour),  -- 칸 9~22 (11-03 A2)
  CONSTRAINT ck_venues_min      CHECK (min_hours BETWEEN 1 AND 4)
) ENGINE=InnoDB;

CREATE TABLE venue_facilities (
  venue_id    BIGINT   NOT NULL,
  facility_id SMALLINT NOT NULL,
  PRIMARY KEY (venue_id, facility_id),
  KEY ix_vf_facility (facility_id, venue_id),     -- '이 시설을 가진 공간' 필터
  CONSTRAINT fk_vf_venue    FOREIGN KEY (venue_id)    REFERENCES venues (venue_id) ON DELETE CASCADE,
  CONSTRAINT fk_vf_facility FOREIGN KEY (facility_id) REFERENCES facilities (facility_id)
) ENGINE=InnoDB;

CREATE TABLE venue_images (
  image_id   BIGINT       NOT NULL AUTO_INCREMENT,
  venue_id   BIGINT       NOT NULL,
  url        VARCHAR(500) NOT NULL,               -- art:<종류>-<색> (예: art:group-0). 크롤링 사진 아님
  sort_order TINYINT      NOT NULL DEFAULT 0,
  PRIMARY KEY (image_id),
  KEY ix_vi_venue (venue_id, sort_order),
  CONSTRAINT fk_vi_venue FOREIGN KEY (venue_id) REFERENCES venues (venue_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ───────── 예약·결제 ─────────

CREATE TABLE reservations (
  reservation_id BIGINT   NOT NULL AUTO_INCREMENT,
  user_id        BIGINT   NOT NULL,
  venue_id       BIGINT   NOT NULL,
  reserve_date   DATE     NOT NULL,
  start_hour     TINYINT  NOT NULL,
  end_hour       TINYINT  NOT NULL,               -- 끝 시각(미포함). 13~15시면 13, 15
  headcount      SMALLINT NOT NULL,
  total_price    INT      NOT NULL,               -- 예약 시점 금액 고정 (의도한 예외)
  status         ENUM('confirmed','completed','cancelled') NOT NULL DEFAULT 'confirmed',
  is_synthetic   BOOLEAN  NOT NULL DEFAULT FALSE,
  created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (reservation_id),
  UNIQUE KEY uq_resv_venue_date (reservation_id, venue_id, reserve_date),  -- slots 복합 외래키 대상
  KEY ix_resv_user (user_id, status, reserve_date),
  KEY ix_resv_venue_date (venue_id, reserve_date),
  KEY ix_resv_status_date (status, reserve_date),  -- 이용 완료 배치
  KEY ix_resv_created (created_at, venue_id),      -- 인기순(최근 7일 예약 수)
  CONSTRAINT fk_resv_user  FOREIGN KEY (user_id)  REFERENCES users (user_id),
  CONSTRAINT fk_resv_venue FOREIGN KEY (venue_id) REFERENCES venues (venue_id),
  CONSTRAINT ck_resv_hours CHECK (start_hour BETWEEN 9 AND 22 AND end_hour <= 23 AND end_hour > start_hour AND end_hour - start_hour <= 4),
  CONSTRAINT ck_resv_head  CHECK (headcount >= 1),
  CONSTRAINT ck_resv_price CHECK (total_price >= 0)
) ENGINE=InnoDB;

CREATE TABLE reservation_slots (
  venue_id       BIGINT  NOT NULL,
  slot_date      DATE    NOT NULL,
  slot_hour      TINYINT NOT NULL,
  reservation_id BIGINT  NOT NULL,
  PRIMARY KEY (venue_id, slot_date, slot_hour),     -- 같은 칸 두 번 예약 금지 (F-32)
  UNIQUE KEY uq_slot_resv (reservation_id, slot_hour),
  CONSTRAINT ck_slot_hour CHECK (slot_hour BETWEEN 9 AND 22),
  CONSTRAINT fk_slot_resv FOREIGN KEY (reservation_id, venue_id, slot_date)
    REFERENCES reservations (reservation_id, venue_id, reserve_date) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE payments (
  payment_id     BIGINT   NOT NULL AUTO_INCREMENT,
  reservation_id BIGINT   NOT NULL,
  method         ENUM('transfer','card','phone') NOT NULL,   -- 계좌이체·카드결제·휴대폰 (명세서 2-3)
  status         ENUM('paid','refunded') NOT NULL DEFAULT 'paid',
  paid_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  refunded_at    DATETIME NULL,
  PRIMARY KEY (payment_id),
  UNIQUE KEY uq_pay_resv (reservation_id),
  CONSTRAINT fk_pay_resv FOREIGN KEY (reservation_id) REFERENCES reservations (reservation_id),
  CONSTRAINT ck_pay_refund CHECK ((status = 'refunded') = (refunded_at IS NOT NULL))
) ENGINE=InnoDB;

-- ───────── 후기 ─────────

CREATE TABLE reviews (
  review_id      BIGINT   NOT NULL AUTO_INCREMENT,
  reservation_id BIGINT   NOT NULL,
  user_id        BIGINT   NOT NULL,
  rating         TINYINT  NOT NULL,
  content        TEXT     NOT NULL,
  created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at     DATETIME NULL,
  PRIMARY KEY (review_id),
  UNIQUE KEY uq_review_resv (reservation_id),        -- 예약 1건당 후기 1개
  KEY ix_review_user (user_id, created_at),
  KEY ix_review_created (created_at),
  CONSTRAINT fk_review_resv FOREIGN KEY (reservation_id) REFERENCES reservations (reservation_id),
  CONSTRAINT fk_review_user FOREIGN KEY (user_id)        REFERENCES users (user_id),
  CONSTRAINT ck_review_rating CHECK (rating BETWEEN 1 AND 5)
) ENGINE=InnoDB;

-- ───────── 운영 ─────────

CREATE TABLE crawl_jobs (
  job_id      BIGINT      NOT NULL AUTO_INCREMENT,
  source_site VARCHAR(30) NOT NULL,
  started_at  DATETIME    NOT NULL,
  finished_at DATETIME    NULL,
  new_ids     INT         NOT NULL DEFAULT 0,      -- 사이트맵에서 새로 찾은 id 수
  fetched     INT         NOT NULL DEFAULT 0,      -- 연 상세 페이지 수 (실행당 20 이하)
  registered  INT         NOT NULL DEFAULT 0,      -- venues에 등록한 수
  status      ENUM('running','done','failed') NOT NULL DEFAULT 'running',
  PRIMARY KEY (job_id),
  KEY ix_crawl_started (source_site, started_at)
) ENGINE=InnoDB;

-- ───────── 뷰 ─────────

CREATE OR REPLACE VIEW v_venue_rating AS
SELECT r.venue_id,
       ROUND(AVG(v.rating), 1) AS rating_avg,
       COUNT(*)                AS review_count
  FROM reviews v
  JOIN reservations r ON r.reservation_id = v.reservation_id
 WHERE v.deleted_at IS NULL
 GROUP BY r.venue_id;

-- ───────── 계정 (비밀번호는 배포 때 넣는다. 이 파일에 적지 않는다) ─────────
-- primary:  app_rw  SELECT, INSERT, UPDATE, DELETE ON spacecube.*
-- replica:  app_ro  SELECT ON spacecube.*            (replica는 read_only=1)
-- 모니터링: exporter PROCESS, REPLICATION CLIENT, SELECT ON *.*  (mysqld_exporter)
