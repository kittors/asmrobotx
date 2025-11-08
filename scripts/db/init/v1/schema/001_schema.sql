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
-- 删除 directory_change_records 表的创建：该表已废弃
-- 保留 operation_log_monitor_rules 的增量列索引创建
ALTER TABLE operation_log_monitor_rules ADD COLUMN IF NOT EXISTS created_by INTEGER NOT NULL DEFAULT 1;
ALTER TABLE operation_log_monitor_rules ADD COLUMN IF NOT EXISTS organization_id INTEGER NOT NULL DEFAULT 1;
CREATE INDEX IF NOT EXISTS idx_operation_log_monitor_rules_created_by ON operation_log_monitor_rules(created_by);
CREATE INDEX IF NOT EXISTS idx_operation_log_monitor_rules_organization_id ON operation_log_monitor_rules(organization_id);

-- ---------------------------------------------------------------------------
-- 统一文件系统节点（目录 + 文件 合表）：高效混排/排序/分页的专用表
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fs_nodes (
    id SERIAL PRIMARY KEY,
    storage_id INTEGER NOT NULL,
    path VARCHAR(1024) NOT NULL,         -- 以 '/' 开头，不以 '/' 结尾
    name VARCHAR(255) NOT NULL,          -- 基名（不含 '/')
    is_dir BOOLEAN NOT NULL DEFAULT FALSE,
    size_bytes BIGINT NOT NULL DEFAULT 0,
    mime_type VARCHAR(255),
    create_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);
-- 审计/隔离列
ALTER TABLE fs_nodes ADD COLUMN IF NOT EXISTS created_by INTEGER NOT NULL DEFAULT 1;
ALTER TABLE fs_nodes ADD COLUMN IF NOT EXISTS organization_id INTEGER NOT NULL DEFAULT 1;
CREATE INDEX IF NOT EXISTS idx_fs_nodes_created_by ON fs_nodes(created_by);
CREATE INDEX IF NOT EXISTS idx_fs_nodes_organization_id ON fs_nodes(organization_id);

-- 局部唯一索引（仅针对未软删除记录），避免重复 path
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes WHERE indexname = 'uq_fs_nodes_storage_path_active'
    ) THEN
        CREATE UNIQUE INDEX uq_fs_nodes_storage_path_active
        ON fs_nodes(storage_id, path)
        WHERE is_deleted = FALSE;
    END IF;
END $$;

-- 常用查询索引
CREATE INDEX IF NOT EXISTS idx_fs_nodes_storage_path ON fs_nodes(storage_id, path);
CREATE INDEX IF NOT EXISTS idx_fs_nodes_storage_name ON fs_nodes(storage_id, name);
CREATE INDEX IF NOT EXISTS idx_fs_nodes_storage_time ON fs_nodes(storage_id, create_time);
CREATE INDEX IF NOT EXISTS idx_fs_nodes_is_dir ON fs_nodes(is_dir);

-- ---------------------------------------------------------------------------
-- 表与字段注释（PostgreSQL COMMENT ON ...）
-- 说明：数据库 GUI/ER 图将读取这些注释展示更丰富的语义信息。
-- ---------------------------------------------------------------------------

-- 组织机构
COMMENT ON TABLE organizations IS '组织机构：支持父子层级（公司/部门），用于归属与数据权限';
COMMENT ON COLUMN organizations.id IS '主键 ID';
COMMENT ON COLUMN organizations.name IS '组织名称（同父节点下唯一）';
COMMENT ON COLUMN organizations.parent_id IS '父组织 ID（自引用；NULL 表示根；硬删除置空）';
COMMENT ON COLUMN organizations.sort_order IS '同级显示排序（升序）';
COMMENT ON COLUMN organizations.created_by IS '创建人用户 ID（默认 1=系统/管理员）';
COMMENT ON COLUMN organizations.create_time IS '创建时间（UTC，数据库默认）';
COMMENT ON COLUMN organizations.update_time IS '更新时间（UTC，自动更新）';
COMMENT ON COLUMN organizations.is_deleted IS '软删除标记（TRUE=已删除）';

-- 角色
COMMENT ON TABLE roles IS '角色：聚合权限并分配给用户，可绑定访问控制项与组织数据范围';
COMMENT ON COLUMN roles.id IS '主键 ID';
COMMENT ON COLUMN roles.name IS '角色名称（唯一）';
COMMENT ON COLUMN roles.role_key IS '角色唯一 Key（英文标识，用于代码/对接）';
COMMENT ON COLUMN roles.sort_order IS '显示排序（升序）';
COMMENT ON COLUMN roles.status IS '状态：normal=正常，disabled=停用';
COMMENT ON COLUMN roles.remark IS '备注说明';
COMMENT ON COLUMN roles.created_by IS '创建人用户 ID（默认 1=系统/管理员）';
COMMENT ON COLUMN roles.organization_id IS '归属组织 ID（多租户/数据隔离）';
COMMENT ON COLUMN roles.create_time IS '创建时间（UTC，数据库默认）';
COMMENT ON COLUMN roles.update_time IS '更新时间（UTC，自动更新）';
COMMENT ON COLUMN roles.is_deleted IS '软删除标记（TRUE=已删除）';

-- 权限
COMMENT ON TABLE permissions IS '权限：系统中可授权的单项能力';
COMMENT ON COLUMN permissions.id IS '主键 ID';
COMMENT ON COLUMN permissions.name IS '权限名称（唯一）';
COMMENT ON COLUMN permissions.description IS '权限描述';
COMMENT ON COLUMN permissions.type IS '权限类型：route | menu | data_scope';
COMMENT ON COLUMN permissions.created_by IS '创建人用户 ID（默认 1=系统/管理员）';
COMMENT ON COLUMN permissions.organization_id IS '归属组织 ID（多租户/数据隔离）';
COMMENT ON COLUMN permissions.create_time IS '创建时间（UTC，数据库默认）';
COMMENT ON COLUMN permissions.update_time IS '更新时间（UTC，自动更新）';
COMMENT ON COLUMN permissions.is_deleted IS '软删除标记（TRUE=已删除）';

-- 用户
COMMENT ON TABLE users IS '用户：系统登录账号，可选隶属某组织并关联多个角色';
COMMENT ON COLUMN users.id IS '主键 ID';
COMMENT ON COLUMN users.username IS '登录用户名（唯一）';
COMMENT ON COLUMN users.hashed_password IS '密码哈希（bcrypt）';
COMMENT ON COLUMN users.nickname IS '昵称';
COMMENT ON COLUMN users.organization_id IS '所属组织 ID';
COMMENT ON COLUMN users.status IS '用户状态：normal=正常，disabled=停用';
COMMENT ON COLUMN users.remark IS '备注说明';
COMMENT ON COLUMN users.is_active IS '是否激活（布尔）';
COMMENT ON COLUMN users.created_by IS '创建人用户 ID（默认 1=系统/管理员）';
COMMENT ON COLUMN users.create_time IS '创建时间（UTC，数据库默认）';
COMMENT ON COLUMN users.update_time IS '更新时间（UTC，自动更新）';
COMMENT ON COLUMN users.is_deleted IS '软删除标记（TRUE=已删除）';

-- 用户-角色（多对多）
COMMENT ON TABLE user_roles IS '关联表：用户-角色 多对多关系（含审计字段）';
COMMENT ON COLUMN user_roles.user_id IS '用户 ID';
COMMENT ON COLUMN user_roles.role_id IS '角色 ID';
COMMENT ON COLUMN user_roles.create_time IS '创建时间（UTC）';
COMMENT ON COLUMN user_roles.update_time IS '更新时间（UTC）';
COMMENT ON COLUMN user_roles.is_deleted IS '软删除标记（TRUE=已删除）';
COMMENT ON COLUMN user_roles.created_by IS '创建人用户 ID（可空）';
COMMENT ON COLUMN user_roles.organization_id IS '归属组织 ID（可空，用于隔离）';

-- 角色-权限（多对多）
COMMENT ON TABLE role_permissions IS '关联表：角色-权限 多对多关系（含审计字段）';
COMMENT ON COLUMN role_permissions.role_id IS '角色 ID';
COMMENT ON COLUMN role_permissions.permission_id IS '权限 ID';
COMMENT ON COLUMN role_permissions.create_time IS '创建时间（UTC）';
COMMENT ON COLUMN role_permissions.update_time IS '更新时间（UTC）';
COMMENT ON COLUMN role_permissions.is_deleted IS '软删除标记（TRUE=已删除）';
COMMENT ON COLUMN role_permissions.created_by IS '创建人用户 ID（可空）';
COMMENT ON COLUMN role_permissions.organization_id IS '归属组织 ID（可空，用于隔离）';

-- 字典类型
COMMENT ON TABLE dictionary_types IS '字典类型：定义一组可配置项的元数据';
COMMENT ON COLUMN dictionary_types.id IS '主键 ID';
COMMENT ON COLUMN dictionary_types.type_code IS '类型编码（唯一，对外引用）';
COMMENT ON COLUMN dictionary_types.display_name IS '类型显示名';
COMMENT ON COLUMN dictionary_types.description IS '类型描述';
COMMENT ON COLUMN dictionary_types.sort_order IS '显示排序（升序）';
COMMENT ON COLUMN dictionary_types.created_by IS '创建人用户 ID（默认 1=系统/管理员）';
COMMENT ON COLUMN dictionary_types.organization_id IS '归属组织 ID（多租户/数据隔离）';
COMMENT ON COLUMN dictionary_types.create_time IS '创建时间（UTC，数据库默认）';
COMMENT ON COLUMN dictionary_types.update_time IS '更新时间（UTC，自动更新）';
COMMENT ON COLUMN dictionary_types.is_deleted IS '软删除标记（TRUE=已删除）';

-- 字典条目
COMMENT ON TABLE dictionary_entries IS '字典条目：按照 type_code 分类存储的选项值';
COMMENT ON COLUMN dictionary_entries.id IS '主键 ID';
COMMENT ON COLUMN dictionary_entries.type_code IS '所属类型编码（FK 到 dictionary_types.type_code）';
COMMENT ON COLUMN dictionary_entries.label IS '显示标签';
COMMENT ON COLUMN dictionary_entries.value IS '存储值';
COMMENT ON COLUMN dictionary_entries.description IS '条目描述';
COMMENT ON COLUMN dictionary_entries.sort_order IS '显示排序（升序）';
COMMENT ON COLUMN dictionary_entries.created_by IS '创建人用户 ID（默认 1=系统/管理员）';
COMMENT ON COLUMN dictionary_entries.organization_id IS '归属组织 ID（多租户/数据隔离）';
COMMENT ON COLUMN dictionary_entries.create_time IS '创建时间（UTC，数据库默认）';
COMMENT ON COLUMN dictionary_entries.update_time IS '更新时间（UTC，自动更新）';
COMMENT ON COLUMN dictionary_entries.is_deleted IS '软删除标记（TRUE=已删除）';

-- 访问控制项（菜单/按钮）
COMMENT ON TABLE access_control_items IS '访问控制项：用于构建前端菜单/按钮等权限树';
COMMENT ON COLUMN access_control_items.id IS '主键 ID';
COMMENT ON COLUMN access_control_items.parent_id IS '父节点 ID（NULL 表示根）';
COMMENT ON COLUMN access_control_items.name IS '名称（菜单/按钮名）';
COMMENT ON COLUMN access_control_items.type IS '节点类型：menu | button';
COMMENT ON COLUMN access_control_items.icon IS '图标（可选）';
COMMENT ON COLUMN access_control_items.is_external IS '是否外链（True=外部跳转）';
COMMENT ON COLUMN access_control_items.permission_code IS '权限编码（唯一，用于后端鉴权/前端显示控制）';
COMMENT ON COLUMN access_control_items.route_path IS '路由路径（前端）';
COMMENT ON COLUMN access_control_items.display_status IS '显示状态（前端枚举，如显示/隐藏）';
COMMENT ON COLUMN access_control_items.enabled_status IS '启用状态（enabled/disabled）';
COMMENT ON COLUMN access_control_items.sort_order IS '显示排序（升序）';
COMMENT ON COLUMN access_control_items.component_path IS '组件路径（前端）';
COMMENT ON COLUMN access_control_items.route_params IS '路由参数（JSON）';
COMMENT ON COLUMN access_control_items.keep_alive IS '是否缓存页面（keep-alive）';
COMMENT ON COLUMN access_control_items.created_by IS '创建人用户 ID（默认 1=系统/管理员）';
COMMENT ON COLUMN access_control_items.organization_id IS '归属组织 ID（多租户/数据隔离）';
COMMENT ON COLUMN access_control_items.create_time IS '创建时间（UTC，数据库默认）';
COMMENT ON COLUMN access_control_items.update_time IS '更新时间（UTC，自动更新）';
COMMENT ON COLUMN access_control_items.is_deleted IS '软删除标记（TRUE=已删除）';

-- 角色-访问控制（多对多）
COMMENT ON TABLE role_access_controls IS '关联表：角色-访问控制项 多对多关系（含审计字段）';
COMMENT ON COLUMN role_access_controls.role_id IS '角色 ID';
COMMENT ON COLUMN role_access_controls.access_control_id IS '访问控制项 ID';
COMMENT ON COLUMN role_access_controls.create_time IS '创建时间（UTC）';
COMMENT ON COLUMN role_access_controls.update_time IS '更新时间（UTC）';
COMMENT ON COLUMN role_access_controls.is_deleted IS '软删除标记（TRUE=已删除）';
COMMENT ON COLUMN role_access_controls.created_by IS '创建人用户 ID（可空）';
COMMENT ON COLUMN role_access_controls.organization_id IS '归属组织 ID（可空，用于隔离）';

-- 角色-组织（数据权限）
COMMENT ON TABLE role_organizations IS '关联表：角色-组织 多对多关系（数据权限授权）';
COMMENT ON COLUMN role_organizations.role_id IS '角色 ID';
COMMENT ON COLUMN role_organizations.organization_id IS '组织 ID（被授权的数据范围）';
COMMENT ON COLUMN role_organizations.create_time IS '创建时间（UTC）';
COMMENT ON COLUMN role_organizations.update_time IS '更新时间（UTC）';
COMMENT ON COLUMN role_organizations.is_deleted IS '软删除标记（TRUE=已删除）';
COMMENT ON COLUMN role_organizations.created_by IS '创建人用户 ID（可空）';
COMMENT ON COLUMN role_organizations.owner_org_id IS '授权记录所属组织 ID（用于多租户隔离）';

-- 操作日志
COMMENT ON TABLE operation_logs IS '操作日志：记录接口调用的关键审计信息';
COMMENT ON COLUMN operation_logs.id IS '主键 ID';
COMMENT ON COLUMN operation_logs.log_number IS '日志唯一编号';
COMMENT ON COLUMN operation_logs.module IS '功能模块名称';
COMMENT ON COLUMN operation_logs.business_type IS '业务类型（create/update/delete/query/grant/export/...）';
COMMENT ON COLUMN operation_logs.operator_name IS '操作人姓名';
COMMENT ON COLUMN operation_logs.operator_department IS '操作人部门';
COMMENT ON COLUMN operation_logs.operator_ip IS '请求 IP 地址';
COMMENT ON COLUMN operation_logs.operator_location IS '地理位置（解析自 IP）';
COMMENT ON COLUMN operation_logs.request_method IS 'HTTP 方法';
COMMENT ON COLUMN operation_logs.request_uri IS '请求 URI';
COMMENT ON COLUMN operation_logs.class_method IS '后端类/方法签名';
COMMENT ON COLUMN operation_logs.request_params IS '请求参数（原样文本/JSON 字符串）';
COMMENT ON COLUMN operation_logs.response_params IS '响应参数（原样文本/JSON 字符串）';
COMMENT ON COLUMN operation_logs.status IS '执行状态：success/failure';
COMMENT ON COLUMN operation_logs.error_message IS '错误信息（失败时）';
COMMENT ON COLUMN operation_logs.cost_ms IS '耗时（毫秒）';
COMMENT ON COLUMN operation_logs.operate_time IS '操作时间（UTC）';
COMMENT ON COLUMN operation_logs.created_by IS '创建人用户 ID（默认 1=系统/管理员）';
COMMENT ON COLUMN operation_logs.organization_id IS '归属组织 ID（多租户/数据隔离）';
COMMENT ON COLUMN operation_logs.create_time IS '创建时间（UTC，数据库默认）';
COMMENT ON COLUMN operation_logs.update_time IS '更新时间（UTC，自动更新）';
COMMENT ON COLUMN operation_logs.is_deleted IS '软删除标记（TRUE=已删除）';

-- 操作日志监听规则
COMMENT ON TABLE operation_log_monitor_rules IS '操作日志监听规则：按 URI/方法 控制采集';
COMMENT ON COLUMN operation_log_monitor_rules.id IS '主键 ID';
COMMENT ON COLUMN operation_log_monitor_rules.name IS '规则名称';
COMMENT ON COLUMN operation_log_monitor_rules.request_uri IS '待匹配的请求 URI';
COMMENT ON COLUMN operation_log_monitor_rules.http_method IS 'HTTP 方法（ALL/GET/POST/...）';
COMMENT ON COLUMN operation_log_monitor_rules.match_mode IS '匹配模式：exact 精确匹配 / prefix 前缀匹配';
COMMENT ON COLUMN operation_log_monitor_rules.is_enabled IS '是否启用';
COMMENT ON COLUMN operation_log_monitor_rules.description IS '规则说明';
COMMENT ON COLUMN operation_log_monitor_rules.operation_type_code IS '业务类型代码（可选，用于统计分类）';
COMMENT ON COLUMN operation_log_monitor_rules.created_by IS '创建人用户 ID（默认 1=系统/管理员）';
COMMENT ON COLUMN operation_log_monitor_rules.organization_id IS '归属组织 ID（多租户/数据隔离）';
COMMENT ON COLUMN operation_log_monitor_rules.create_time IS '创建时间（UTC，数据库默认）';
COMMENT ON COLUMN operation_log_monitor_rules.update_time IS '更新时间（UTC，自动更新）';
COMMENT ON COLUMN operation_log_monitor_rules.is_deleted IS '软删除标记（TRUE=已删除）';

-- 登录日志
COMMENT ON TABLE login_logs IS '登录日志：记录系统访问行为';
COMMENT ON COLUMN login_logs.id IS '主键 ID';
COMMENT ON COLUMN login_logs.visit_number IS '访问唯一编号';
COMMENT ON COLUMN login_logs.username IS '登录用户名';
COMMENT ON COLUMN login_logs.client_name IS '客户端名称（应用/渠道）';
COMMENT ON COLUMN login_logs.device_type IS '设备类型';
COMMENT ON COLUMN login_logs.ip_address IS 'IP 地址';
COMMENT ON COLUMN login_logs.login_location IS '登录地（解析自 IP）';
COMMENT ON COLUMN login_logs.operating_system IS '操作系统';
COMMENT ON COLUMN login_logs.browser IS '浏览器';
COMMENT ON COLUMN login_logs.status IS '状态：success/failure';
COMMENT ON COLUMN login_logs.message IS '提示信息/异常描述';
COMMENT ON COLUMN login_logs.login_time IS '登录时间（UTC）';
COMMENT ON COLUMN login_logs.created_by IS '创建人用户 ID（默认 1=系统/管理员）';
COMMENT ON COLUMN login_logs.organization_id IS '归属组织 ID（多租户/数据隔离）';
COMMENT ON COLUMN login_logs.create_time IS '创建时间（UTC，数据库默认）';
COMMENT ON COLUMN login_logs.update_time IS '更新时间（UTC，自动更新）';
COMMENT ON COLUMN login_logs.is_deleted IS '软删除标记（TRUE=已删除）';

-- 存储源配置
COMMENT ON TABLE storage_configs IS '存储源配置：S3 或本地文件系统的连接与直链参数';
COMMENT ON COLUMN storage_configs.id IS '主键 ID';
COMMENT ON COLUMN storage_configs.name IS '配置名称（唯一）';
COMMENT ON COLUMN storage_configs.config_key IS '外部引用用的唯一 key（可选）';
COMMENT ON COLUMN storage_configs.type IS '存储类型：S3 | LOCAL';
COMMENT ON COLUMN storage_configs.region IS 'S3 区域（Region）';
COMMENT ON COLUMN storage_configs.bucket_name IS 'S3 桶名（Bucket）';
COMMENT ON COLUMN storage_configs.path_prefix IS 'S3 路径前缀（可选）';
COMMENT ON COLUMN storage_configs.access_key_id IS 'S3 访问 Key ID';
COMMENT ON COLUMN storage_configs.secret_access_key IS 'S3 访问 Secret Key';
COMMENT ON COLUMN storage_configs.endpoint_url IS 'S3 兼容端点（MinIO/厂商自定义）';
COMMENT ON COLUMN storage_configs.custom_domain IS '自定义访问域名/CDN 域名';
COMMENT ON COLUMN storage_configs.use_https IS '直链是否使用 HTTPS';
COMMENT ON COLUMN storage_configs.acl_type IS 'ACL 类型：private | public | custom';
COMMENT ON COLUMN storage_configs.local_root_path IS '本地根目录（LOCAL 类型）';
COMMENT ON COLUMN storage_configs.created_by IS '创建人用户 ID（默认 1=系统/管理员）';
COMMENT ON COLUMN storage_configs.organization_id IS '归属组织 ID（多租户/数据隔离）';
COMMENT ON COLUMN storage_configs.create_time IS '创建时间（UTC，数据库默认）';
COMMENT ON COLUMN storage_configs.update_time IS '更新时间（UTC，自动更新）';
COMMENT ON COLUMN storage_configs.is_deleted IS '软删除标记（TRUE=已删除）';

-- 文件记录
COMMENT ON TABLE file_records IS '文件记录：保存上传文件的元数据（原名/别名/用途）';
COMMENT ON COLUMN file_records.id IS '主键 ID';
COMMENT ON COLUMN file_records.storage_id IS '存储源 ID（关联 storage_configs.id）';
COMMENT ON COLUMN file_records.directory IS '目录路径（以“/”开头；不包含文件名）';
COMMENT ON COLUMN file_records.original_name IS '上传时的原始文件名';
COMMENT ON COLUMN file_records.alias_name IS '实际存储使用的文件名（含去重后别名）';
COMMENT ON COLUMN file_records.purpose IS '上传用途（如 avatar/general/attachment 等）';
COMMENT ON COLUMN file_records.size_bytes IS '文件大小（字节）';
COMMENT ON COLUMN file_records.mime_type IS 'MIME 类型（可空）';
COMMENT ON COLUMN file_records.created_by IS '创建人用户 ID（默认 1=系统/管理员）';
COMMENT ON COLUMN file_records.organization_id IS '归属组织 ID（多租户/数据隔离）';
COMMENT ON COLUMN file_records.create_time IS '创建时间（UTC，数据库默认）';
COMMENT ON COLUMN file_records.update_time IS '更新时间（UTC，自动更新）';
COMMENT ON COLUMN file_records.is_deleted IS '软删除标记（TRUE=已删除）';

-- 统一文件系统节点（目录 + 文件）
COMMENT ON TABLE fs_nodes IS '统一文件系统节点：目录与文件合表，便于混排/排序/分页';
COMMENT ON COLUMN fs_nodes.id IS '主键 ID';
COMMENT ON COLUMN fs_nodes.storage_id IS '存储源 ID（关联 storage_configs.id）';
COMMENT ON COLUMN fs_nodes.path IS '路径（以“/”开头，不以“/”结尾；根目录不入库）';
COMMENT ON COLUMN fs_nodes.name IS '基名（不含“/”）';
COMMENT ON COLUMN fs_nodes.is_dir IS '是否为目录（True=目录，False=文件）';
COMMENT ON COLUMN fs_nodes.size_bytes IS '文件大小（字节；目录固定为 0）';
COMMENT ON COLUMN fs_nodes.mime_type IS 'MIME 类型（文件有效；目录为 NULL）';
COMMENT ON COLUMN fs_nodes.created_by IS '创建人用户 ID（默认 1=系统/管理员）';
COMMENT ON COLUMN fs_nodes.organization_id IS '归属组织 ID（多租户/数据隔离）';
COMMENT ON COLUMN fs_nodes.create_time IS '创建时间（UTC，数据库默认）';
COMMENT ON COLUMN fs_nodes.update_time IS '更新时间（UTC，自动更新）';
COMMENT ON COLUMN fs_nodes.is_deleted IS '软删除标记（TRUE=已删除）';
