-- Database initialization aggregator for version v1
-- This file is executed by Postgres docker-entrypoint.
-- It includes schema first, then data.
\set ON_ERROR_STOP on

-- Schema (tables, indexes, extensions)
\ir v1/schema/001_schema.sql

-- Data seeds (must run after schema)
\ir v1/data/001_seed_data.sql
