CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS organizations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    create_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);
-- 增量列：组织层级、排序与创建人
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS parent_id INTEGER;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS sort_order INTEGER NOT NULL DEFAULT 0;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS created_by INTEGER NOT NULL DEFAULT 1;
-- 约束与索引
-- 同一个父节点下，名称唯一（允许不同父节点重名）
DO $$ BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'organizations_name_key'
    ) THEN
        ALTER TABLE organizations DROP CONSTRAINT organizations_name_key;
    END IF;
END $$;
CREATE UNIQUE INDEX IF NOT EXISTS uq_organizations_parent_name ON organizations(parent_id, name);
-- 防止自引用
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_organizations_no_self_parent'
    ) THEN
        ALTER TABLE organizations
            ADD CONSTRAINT ck_organizations_no_self_parent CHECK (parent_id IS NULL OR parent_id <> id);
    END IF;
END $$;
-- 自引用外键（硬删除置空；业务使用软删除）
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_organizations_parent_id'
    ) THEN
        ALTER TABLE organizations
            ADD CONSTRAINT fk_organizations_parent_id FOREIGN KEY (parent_id) REFERENCES organizations(id) ON DELETE SET NULL;
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS idx_organizations_parent_id ON organizations(parent_id);
CREATE INDEX IF NOT EXISTS idx_organizations_sort_order ON organizations(sort_order);
CREATE INDEX IF NOT EXISTS idx_organizations_created_by ON organizations(created_by);

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
ALTER TABLE roles ADD COLUMN IF NOT EXISTS created_by INTEGER NOT NULL DEFAULT 1;
ALTER TABLE roles ADD COLUMN IF NOT EXISTS organization_id INTEGER NOT NULL DEFAULT 1;
CREATE INDEX IF NOT EXISTS idx_roles_created_by ON roles(created_by);
CREATE INDEX IF NOT EXISTS idx_roles_organization_id ON roles(organization_id);

CREATE TABLE IF NOT EXISTS permissions (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    description VARCHAR(255),
    type VARCHAR(50) NOT NULL,
    create_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);
ALTER TABLE permissions ADD COLUMN IF NOT EXISTS created_by INTEGER NOT NULL DEFAULT 1;
ALTER TABLE permissions ADD COLUMN IF NOT EXISTS organization_id INTEGER NOT NULL DEFAULT 1;
CREATE INDEX IF NOT EXISTS idx_permissions_created_by ON permissions(created_by);
CREATE INDEX IF NOT EXISTS idx_permissions_organization_id ON permissions(organization_id);

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
ALTER TABLE users ADD COLUMN IF NOT EXISTS created_by INTEGER NOT NULL DEFAULT 1;
CREATE INDEX IF NOT EXISTS idx_users_created_by ON users(created_by);

CREATE TABLE IF NOT EXISTS user_roles (
    user_id INTEGER,
    role_id INTEGER,
    PRIMARY KEY (user_id, role_id)
);
-- 关联表补充审计/隔离列
ALTER TABLE user_roles ADD COLUMN IF NOT EXISTS create_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE user_roles ADD COLUMN IF NOT EXISTS update_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE user_roles ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE user_roles ADD COLUMN IF NOT EXISTS created_by INTEGER NOT NULL DEFAULT 1;
ALTER TABLE user_roles ADD COLUMN IF NOT EXISTS organization_id INTEGER NOT NULL DEFAULT 1;
CREATE INDEX IF NOT EXISTS idx_user_roles_created_by ON user_roles(created_by);
CREATE INDEX IF NOT EXISTS idx_user_roles_organization_id ON user_roles(organization_id);

CREATE TABLE IF NOT EXISTS role_permissions (
    role_id INTEGER,
    permission_id INTEGER,
    PRIMARY KEY (role_id, permission_id)
);
ALTER TABLE role_permissions ADD COLUMN IF NOT EXISTS create_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE role_permissions ADD COLUMN IF NOT EXISTS update_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE role_permissions ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE role_permissions ADD COLUMN IF NOT EXISTS created_by INTEGER NOT NULL DEFAULT 1;
ALTER TABLE role_permissions ADD COLUMN IF NOT EXISTS organization_id INTEGER NOT NULL DEFAULT 1;
CREATE INDEX IF NOT EXISTS idx_role_permissions_created_by ON role_permissions(created_by);
CREATE INDEX IF NOT EXISTS idx_role_permissions_organization_id ON role_permissions(organization_id);

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
-- 增量列：审计与组织归属
ALTER TABLE dictionary_types ADD COLUMN IF NOT EXISTS created_by INTEGER NOT NULL DEFAULT 1;
ALTER TABLE dictionary_types ADD COLUMN IF NOT EXISTS organization_id INTEGER NOT NULL DEFAULT 1;
CREATE INDEX IF NOT EXISTS idx_dictionary_types_created_by ON dictionary_types(created_by);
CREATE INDEX IF NOT EXISTS idx_dictionary_types_organization_id ON dictionary_types(organization_id);

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
ALTER TABLE dictionary_entries ADD COLUMN IF NOT EXISTS created_by INTEGER NOT NULL DEFAULT 1;
ALTER TABLE dictionary_entries ADD COLUMN IF NOT EXISTS organization_id INTEGER NOT NULL DEFAULT 1;
CREATE INDEX IF NOT EXISTS idx_dictionary_entries_created_by ON dictionary_entries(created_by);
CREATE INDEX IF NOT EXISTS idx_dictionary_entries_organization_id ON dictionary_entries(organization_id);

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
ALTER TABLE access_control_items ADD COLUMN IF NOT EXISTS created_by INTEGER NOT NULL DEFAULT 1;
ALTER TABLE access_control_items ADD COLUMN IF NOT EXISTS organization_id INTEGER NOT NULL DEFAULT 1;
CREATE INDEX IF NOT EXISTS idx_access_control_items_created_by ON access_control_items(created_by);
CREATE INDEX IF NOT EXISTS idx_access_control_items_organization_id ON access_control_items(organization_id);

CREATE TABLE IF NOT EXISTS role_access_controls (
    role_id INTEGER,
    access_control_id INTEGER,
    PRIMARY KEY (role_id, access_control_id)
);
ALTER TABLE role_access_controls ADD COLUMN IF NOT EXISTS create_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE role_access_controls ADD COLUMN IF NOT EXISTS update_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE role_access_controls ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE role_access_controls ADD COLUMN IF NOT EXISTS created_by INTEGER NOT NULL DEFAULT 1;
ALTER TABLE role_access_controls ADD COLUMN IF NOT EXISTS organization_id INTEGER NOT NULL DEFAULT 1;
CREATE INDEX IF NOT EXISTS idx_role_access_controls_created_by ON role_access_controls(created_by);
CREATE INDEX IF NOT EXISTS idx_role_access_controls_organization_id ON role_access_controls(organization_id);

-- 角色-组织（数据权限）
CREATE TABLE IF NOT EXISTS role_organizations (
    role_id INTEGER,
    organization_id INTEGER,
    PRIMARY KEY (role_id, organization_id)
);
ALTER TABLE role_organizations ADD COLUMN IF NOT EXISTS create_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE role_organizations ADD COLUMN IF NOT EXISTS update_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE role_organizations ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE role_organizations ADD COLUMN IF NOT EXISTS created_by INTEGER NOT NULL DEFAULT 1;
ALTER TABLE role_organizations ADD COLUMN IF NOT EXISTS owner_org_id INTEGER NOT NULL DEFAULT 1;
CREATE INDEX IF NOT EXISTS idx_role_organizations_created_by ON role_organizations(created_by);
CREATE INDEX IF NOT EXISTS idx_role_organizations_owner_org_id ON role_organizations(owner_org_id);

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
ALTER TABLE operation_logs ADD COLUMN IF NOT EXISTS created_by INTEGER NOT NULL DEFAULT 1;
ALTER TABLE operation_logs ADD COLUMN IF NOT EXISTS organization_id INTEGER NOT NULL DEFAULT 1;
CREATE INDEX IF NOT EXISTS idx_operation_logs_created_by ON operation_logs(created_by);
CREATE INDEX IF NOT EXISTS idx_operation_logs_organization_id ON operation_logs(organization_id);

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
ALTER TABLE login_logs ADD COLUMN IF NOT EXISTS created_by INTEGER NOT NULL DEFAULT 1;
ALTER TABLE login_logs ADD COLUMN IF NOT EXISTS organization_id INTEGER NOT NULL DEFAULT 1;
CREATE INDEX IF NOT EXISTS idx_login_logs_created_by ON login_logs(created_by);
CREATE INDEX IF NOT EXISTS idx_login_logs_organization_id ON login_logs(organization_id);

-- 数据初始化相关的 INSERT 语句已迁移至 scripts/db/init/v1/data/001_seed_data.sql。

-- ---------------------------------------------------------------------------
-- 文件管理：存储源配置表
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS storage_configs (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    config_key VARCHAR(64) UNIQUE, -- 对外引用用的唯一 key（可选但建议提供）
    type VARCHAR(16) NOT NULL, -- 'S3' | 'LOCAL'
    region VARCHAR(64), -- S3 only
    bucket_name VARCHAR(128), -- S3 only
    path_prefix VARCHAR(255), -- S3 only
    access_key_id VARCHAR(128), -- S3 only
    secret_access_key VARCHAR(256), -- S3 only
    endpoint_url VARCHAR(255), -- S3 only，自定义兼容端点（MinIO/厂商 S3）
    custom_domain VARCHAR(255), -- S3 only，自定义访问域名/CDN 域名
    use_https BOOLEAN NOT NULL DEFAULT TRUE, -- S3 only，直链拼接是否 https
    acl_type VARCHAR(16) NOT NULL DEFAULT 'private', -- S3 only，'private' | 'public' | 'custom'
    local_root_path VARCHAR(512), -- LOCAL only
    create_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT ck_storage_configs_acl_type CHECK (acl_type IN ('private','public','custom'))
);

-- 向后兼容：增量添加缺失列
ALTER TABLE storage_configs ADD COLUMN IF NOT EXISTS config_key VARCHAR(64);
ALTER TABLE storage_configs ADD COLUMN IF NOT EXISTS endpoint_url VARCHAR(255);
ALTER TABLE storage_configs ADD COLUMN IF NOT EXISTS custom_domain VARCHAR(255);
ALTER TABLE storage_configs ADD COLUMN IF NOT EXISTS use_https BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE storage_configs ADD COLUMN IF NOT EXISTS acl_type VARCHAR(16) NOT NULL DEFAULT 'private';
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_storage_configs_acl_type'
    ) THEN
        ALTER TABLE storage_configs ADD CONSTRAINT ck_storage_configs_acl_type CHECK (acl_type IN ('private','public','custom'));
    END IF;
END $$;
ALTER TABLE storage_configs ADD COLUMN IF NOT EXISTS created_by INTEGER NOT NULL DEFAULT 1;
ALTER TABLE storage_configs ADD COLUMN IF NOT EXISTS organization_id INTEGER NOT NULL DEFAULT 1;
CREATE INDEX IF NOT EXISTS idx_storage_configs_created_by ON storage_configs(created_by);
CREATE INDEX IF NOT EXISTS idx_storage_configs_organization_id ON storage_configs(organization_id);

-- ---------------------------------------------------------------------------
-- 文件记录：保存上传文件的元数据（原名、别名、用途）。
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS file_records (
    id SERIAL PRIMARY KEY,
    storage_id INTEGER NOT NULL,
    directory VARCHAR(1024) NOT NULL, -- 目录路径，以 '/' 开头，末尾不包含文件名
    original_name VARCHAR(255) NOT NULL, -- 上传时的原始文件名
    alias_name VARCHAR(255) NOT NULL, -- 实际存储使用的文件名（含自动去重的别名）
    purpose VARCHAR(64) NOT NULL DEFAULT 'general', -- 上传用途
    size_bytes BIGINT NOT NULL DEFAULT 0,
    mime_type VARCHAR(255),
    create_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);
ALTER TABLE file_records ADD COLUMN IF NOT EXISTS created_by INTEGER NOT NULL DEFAULT 1;
ALTER TABLE file_records ADD COLUMN IF NOT EXISTS organization_id INTEGER NOT NULL DEFAULT 1;
CREATE INDEX IF NOT EXISTS idx_file_records_created_by ON file_records(created_by);
CREATE INDEX IF NOT EXISTS idx_file_records_organization_id ON file_records(organization_id);

CREATE INDEX IF NOT EXISTS idx_file_records_storage_dir ON file_records(storage_id, directory);
CREATE INDEX IF NOT EXISTS idx_file_records_purpose ON file_records(purpose);

-- ---------------------------------------------------------------------------
-- 本地目录变更记录：用于从本地存储根目录下的“记录文件”导入到数据库
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS directory_change_records (
    id SERIAL PRIMARY KEY,
    storage_id INTEGER NOT NULL,
    action VARCHAR(32) NOT NULL, -- create | rename | move | delete | copy
    path_old VARCHAR(1024),
    path_new VARCHAR(1024),
    operate_time TIMESTAMPTZ NOT NULL,
    extra JSONB,
    create_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);
ALTER TABLE directory_change_records ADD COLUMN IF NOT EXISTS created_by INTEGER NOT NULL DEFAULT 1;
ALTER TABLE directory_change_records ADD COLUMN IF NOT EXISTS organization_id INTEGER NOT NULL DEFAULT 1;
CREATE INDEX IF NOT EXISTS idx_directory_change_records_created_by ON directory_change_records(created_by);
CREATE INDEX IF NOT EXISTS idx_directory_change_records_organization_id ON directory_change_records(organization_id);

-- 保证幂等导入：同一条记录不会重复插入
CREATE UNIQUE INDEX IF NOT EXISTS uq_directory_change_records_dedup
ON directory_change_records(storage_id, action, COALESCE(path_old, ''), COALESCE(path_new, ''), operate_time)
WHERE is_deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_directory_change_records_storage ON directory_change_records(storage_id);
ALTER TABLE operation_log_monitor_rules ADD COLUMN IF NOT EXISTS created_by INTEGER NOT NULL DEFAULT 1;
ALTER TABLE operation_log_monitor_rules ADD COLUMN IF NOT EXISTS organization_id INTEGER NOT NULL DEFAULT 1;
CREATE INDEX IF NOT EXISTS idx_operation_log_monitor_rules_created_by ON operation_log_monitor_rules(created_by);
CREATE INDEX IF NOT EXISTS idx_operation_log_monitor_rules_organization_id ON operation_log_monitor_rules(organization_id);
