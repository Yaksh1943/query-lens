-- Runs first (filename-ordered) on first container startup.
-- The app's own database (app_db) is created automatically via the
-- POSTGRES_DB env var in docker-compose.yml; this creates the second
-- database that the Text-to-SQL engine queries against.
CREATE DATABASE chinook;
