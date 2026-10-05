-- ===========================================================
--   Fake Instagram Account Detection — MySQL Setup
-- ===========================================================
-- Run BEFORE first migrate:
--   mysql -u root -p < setup_db.sql
-- Then run Django migrations to create tables.

CREATE DATABASE IF NOT EXISTS fakeinsta_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- Optional: dedicated user
-- CREATE USER 'fakeinsta'@'localhost' IDENTIFIED BY 'change_me';
-- GRANT ALL PRIVILEGES ON fakeinsta_db.* TO 'fakeinsta'@'localhost';
-- FLUSH PRIVILEGES;

USE fakeinsta_db;
SHOW TABLES;
