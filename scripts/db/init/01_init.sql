CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS organizations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    create_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    role_key VARCHAR(100) UNIQUE NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'normal',
    remark VARCHAR(255),
    create_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS permissions (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    description VARCHAR(255),
    type VARCHAR(50) NOT NULL,
    create_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    nickname VARCHAR(100),
    organization_id INTEGER,
    status VARCHAR(20) NOT NULL DEFAULT 'normal',
    remark VARCHAR(255),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    create_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS user_roles (
    user_id INTEGER,
    role_id INTEGER,
    PRIMARY KEY (user_id, role_id)
);

CREATE TABLE IF NOT EXISTS role_permissions (
    role_id INTEGER,
    permission_id INTEGER,
    PRIMARY KEY (role_id, permission_id)
);

-- ---------------------------------------------------------------------------
-- 字典类型与字典项：用于维护前端通用的下拉/图标等可配置选项。
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dictionary_types (
    id SERIAL PRIMARY KEY,
    type_code VARCHAR(100) UNIQUE NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    description VARCHAR(255),
    sort_order INTEGER NOT NULL DEFAULT 0,
    create_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS dictionary_entries (
    id SERIAL PRIMARY KEY,
    type_code VARCHAR(100) NOT NULL,
    label VARCHAR(100) NOT NULL,
    value VARCHAR(100) NOT NULL,
    description VARCHAR(255),
    sort_order INTEGER NOT NULL DEFAULT 0,
    create_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT uq_dictionary_entries_type_value UNIQUE (type_code, value),
    CONSTRAINT fk_dictionary_entries_type FOREIGN KEY (type_code) REFERENCES dictionary_types (type_code)
);

CREATE TABLE IF NOT EXISTS access_control_items (
    id SERIAL PRIMARY KEY,
    parent_id INTEGER,
    name VARCHAR(100) NOT NULL,
    type VARCHAR(20) NOT NULL DEFAULT 'menu',
    icon VARCHAR(100),
    is_external BOOLEAN NOT NULL DEFAULT FALSE,
    permission_code VARCHAR(100),
    route_path VARCHAR(255),
    display_status VARCHAR(50),
    enabled_status VARCHAR(50) NOT NULL DEFAULT 'enabled',
    sort_order INTEGER NOT NULL DEFAULT 0,
    component_path VARCHAR(255),
    route_params JSONB,
    keep_alive BOOLEAN NOT NULL DEFAULT FALSE,
    create_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT uq_access_control_items_permission_code UNIQUE (permission_code)
);

CREATE TABLE IF NOT EXISTS role_access_controls (
    role_id INTEGER,
    access_control_id INTEGER,
    PRIMARY KEY (role_id, access_control_id)
);

CREATE TABLE IF NOT EXISTS operation_logs (
    id SERIAL PRIMARY KEY,
    log_number VARCHAR(32) UNIQUE NOT NULL,
    module VARCHAR(100) NOT NULL,
    business_type VARCHAR(32) NOT NULL,
    operator_name VARCHAR(50) NOT NULL,
    operator_department VARCHAR(100),
    operator_ip VARCHAR(64),
    operator_location VARCHAR(255),
    request_method VARCHAR(16),
    request_uri VARCHAR(255),
    class_method VARCHAR(255),
    request_params TEXT,
    response_params TEXT,
    status VARCHAR(16) NOT NULL DEFAULT 'success',
    error_message TEXT,
    cost_ms INTEGER NOT NULL DEFAULT 0,
    operate_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    create_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS operation_log_monitor_rules (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    request_uri VARCHAR(255) NOT NULL,
    http_method VARCHAR(16) NOT NULL DEFAULT 'ALL',
    match_mode VARCHAR(16) NOT NULL DEFAULT 'exact',
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    description VARCHAR(255),
    operation_type_code VARCHAR(32),
    create_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT ck_operation_log_monitor_rules_mode CHECK (match_mode IN ('exact', 'prefix')),
    CONSTRAINT ck_operation_log_monitor_rules_method CHECK (http_method <> '')
);

ALTER TABLE operation_log_monitor_rules
    ADD COLUMN IF NOT EXISTS operation_type_code VARCHAR(32);

ALTER TABLE operation_log_monitor_rules
    DROP COLUMN IF EXISTS operation_type_label;

CREATE UNIQUE INDEX IF NOT EXISTS uq_operation_log_monitor_rules_active
ON operation_log_monitor_rules(request_uri, http_method, match_mode)
WHERE is_deleted = FALSE;

CREATE TABLE IF NOT EXISTS login_logs (
    id SERIAL PRIMARY KEY,
    visit_number VARCHAR(32) UNIQUE NOT NULL,
    username VARCHAR(50) NOT NULL,
    client_name VARCHAR(100),
    device_type VARCHAR(50),
    ip_address VARCHAR(64),
    login_location VARCHAR(255),
    operating_system VARCHAR(100),
    browser VARCHAR(100),
    status VARCHAR(16) NOT NULL DEFAULT 'success',
    message VARCHAR(255),
    login_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    create_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);

-- 数据初始化相关的 INSERT 语句已迁移至 scripts/db/init/02_seed_data.sql。
