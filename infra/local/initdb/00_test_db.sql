-- 첫 실행 때 자동으로 돈다. 테스트 스키마는 비워 두고, db/tests/check_ddl.py가 0001로 새로 만든다.
CREATE DATABASE IF NOT EXISTS spacecube_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON spacecube_test.* TO 'app'@'%';
