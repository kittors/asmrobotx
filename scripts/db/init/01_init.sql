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
-- 字典表：用于维护前端通用的下拉/图标等可配置选项，便于通过 type_code 分类检索。
-- ---------------------------------------------------------------------------
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
    CONSTRAINT uq_dictionary_entries_type_value UNIQUE (type_code, value)
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

INSERT INTO operation_log_monitor_rules (
    name,
    request_uri,
    http_method,
    match_mode,
    is_enabled,
    description,
    operation_type_code
)
SELECT
    '接口调用日志列表',
    '/api/v1/logs/operations',
    'ALL',
    'prefix',
    FALSE,
    '获取接口调用的日志列表',
    'query'
WHERE NOT EXISTS (
    SELECT 1
    FROM operation_log_monitor_rules
    WHERE request_uri = '/api/v1/logs/operations'
      AND http_method = 'ALL'
      AND match_mode = 'prefix'
);

INSERT INTO organizations (name)
VALUES ('研发部')
ON CONFLICT (name) DO NOTHING;

INSERT INTO roles (name, role_key, sort_order, status)
VALUES ('admin', 'admin', 1, 'normal')
ON CONFLICT (name) DO NOTHING;
INSERT INTO roles (name, role_key, sort_order, status)
VALUES ('user', 'user', 2, 'normal')
ON CONFLICT (name) DO NOTHING;

INSERT INTO permissions (name, description, type)
VALUES
    ('view_dashboard', '查看仪表盘', 'route'),
    ('edit_self_profile', '编辑个人资料', 'route'),
    ('manage_users', '管理用户', 'route')
ON CONFLICT (name) DO NOTHING;

INSERT INTO users (username, hashed_password, nickname, organization_id, status, remark, is_active)
VALUES (
    'admin',
    crypt('admin123', gen_salt('bf')),
    '系统管理员',
    (SELECT id FROM organizations WHERE name = '研发部'),
    'normal',
    NULL,
    TRUE
)
ON CONFLICT (username) DO NOTHING;

INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id FROM users u, roles r
WHERE u.username = 'admin' AND r.name = 'admin'
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.name = 'admin' AND p.name IN ('view_dashboard', 'edit_self_profile', 'manage_users')
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.name = 'user' AND p.name IN ('view_dashboard', 'edit_self_profile')
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------------
-- 图标字典：为前端图标选择器提供常用候选项，可持续扩充。
-- ---------------------------------------------------------------------------
INSERT INTO dictionary_entries (type_code, label, value, description, sort_order)
VALUES
    ('icon_list', '工具箱', 'tool-case', '工具图标', 1),
    ('icon_list', '设置', 'settings', '设置图标', 2),
    ('icon_list', '搜索', 'search', '通用搜索图标', 3),
    ('icon_list', '外链', 'link', '外链/跳转图标', 4),
    ('icon_list', '地图定位', 'map-pinned', '地理定位图标', 5),
    ('icon_list', '菜单', 'menu', '菜单/列表图标', 6)
ON CONFLICT (type_code, value) DO NOTHING;

INSERT INTO dictionary_entries (type_code, label, value, description, sort_order)
VALUES
    ('operation_log_type', '新增', 'create', '新增数据', 1),
    ('operation_log_type', '修改', 'update', '修改数据', 2),
    ('operation_log_type', '删除', 'delete', '删除数据', 3),
    ('operation_log_type', '查询', 'query', '查询数据', 4),
    ('operation_log_type', '授权', 'grant', '权限授权', 5),
    ('operation_log_type', '导出', 'export', '数据导出', 6),
    ('operation_log_type', '导入', 'import', '数据导入', 7),
    ('operation_log_type', '强退', 'force_logout', '强制下线', 8),
    ('operation_log_type', '清除数据', 'clean', '批量清除数据', 9),
    ('operation_log_type', '其他', 'other', '其它操作', 10)
ON CONFLICT (type_code, value) DO NOTHING;

INSERT INTO access_control_items (
    id, parent_id, name, type, icon, is_external, permission_code, route_path,
    display_status, enabled_status, sort_order, component_path, route_params, keep_alive
)
VALUES
    (1, NULL, '系统管理', 'menu', 'settings', FALSE, NULL, 'system', 'show', 'enabled', 0, NULL, '{}'::jsonb, FALSE),
    (2, 1, '用户管理', 'menu', 'tool-case', FALSE, 'system:user:list', 'user', 'show', 'enabled', 0, 'system/user/index', '{}'::jsonb, FALSE),
    (3, 2, '用户查询', 'button', NULL, FALSE, 'system:user:query', NULL, NULL, 'enabled', 0, NULL, '{}'::jsonb, FALSE),
    (4, 2, '用户新增', 'button', NULL, FALSE, 'system:user:add', NULL, NULL, 'enabled', 0, NULL, '{}'::jsonb, FALSE),
    (5, 2, '用户修改', 'button', NULL, FALSE, 'system:user:edit', NULL, NULL, 'enabled', 0, NULL, '{}'::jsonb, FALSE),
    (6, 2, '用户删除', 'button', NULL, FALSE, 'system:user:remove', NULL, NULL, 'enabled', 0, NULL, '{}'::jsonb, FALSE),
    (7, 2, '用户导出', 'button', NULL, FALSE, 'system:user:export', NULL, NULL, 'enabled', 0, NULL, '{}'::jsonb, FALSE),
    (8, 2, '用户导入', 'button', NULL, FALSE, 'system:user:import', NULL, NULL, 'enabled', 0, NULL, '{}'::jsonb, FALSE),
    (9, 2, '重置密码', 'button', NULL, FALSE, 'system:user:resetPwd', NULL, NULL, 'enabled', 0, NULL, '{}'::jsonb, FALSE),
    (10, 1, '角色管理', 'menu', 'settings', FALSE, 'system:role:list', 'role', 'show', 'enabled', 0, 'system/role/index', '{}'::jsonb, FALSE),
    (11, 10, '角色查询', 'button', NULL, FALSE, 'system:role:query', NULL, NULL, 'enabled', 0, NULL, '{}'::jsonb, FALSE),
    (12, 10, '角色新增', 'button', NULL, FALSE, 'system:role:add', NULL, NULL, 'enabled', 0, NULL, '{}'::jsonb, FALSE),
    (13, 10, '角色修改', 'button', NULL, FALSE, 'system:role:edit', NULL, NULL, 'enabled', 0, NULL, '{}'::jsonb, FALSE),
    (14, 10, '角色删除', 'button', NULL, FALSE, 'system:role:remove', NULL, NULL, 'enabled', 0, NULL, '{}'::jsonb, FALSE),
    (15, 10, '角色导出', 'button', NULL, FALSE, 'system:role:export', NULL, NULL, 'enabled', 0, NULL, '{}'::jsonb, FALSE),
    (26, 1, '访问管理', 'menu', 'settings', FALSE, 'system:accessControl:list', 'accessControl', 'show', 'enabled', 0, 'system/AccessControl/index', '{}'::jsonb, FALSE),
    (16, 1, '日志管理', 'menu', 'settings', FALSE, NULL, 'log', 'show', 'enabled', 0, NULL, '{}'::jsonb, FALSE),
    (17, 16, '操作日志', 'menu', 'settings', FALSE, 'monitor:operlog:list', 'operlog', 'show', 'enabled', 0, 'system/monitor/operlog/index', '{}'::jsonb, FALSE),
    (18, 16, '登录日志', 'menu', NULL, FALSE, 'monitor:logininfor:list', 'logininfor', 'show', 'enabled', 0, 'system/monitor/logininfor/index', '{}'::jsonb, FALSE),
    (19, 17, '操作查询', 'button', NULL, FALSE, 'monitor:operlog:query', NULL, NULL, 'enabled', 0, NULL, '{}'::jsonb, FALSE),
    (20, 17, '操作删除', 'button', NULL, FALSE, 'monitor:operlog:remove', NULL, NULL, 'enabled', 0, NULL, '{}'::jsonb, FALSE),
    (21, 17, '日志导出', 'button', NULL, FALSE, 'monitor:operlog:export', NULL, NULL, 'enabled', 0, NULL, '{}'::jsonb, FALSE),
    (22, 18, '登录查询', 'button', NULL, FALSE, 'monitor:logininfor:query', NULL, NULL, 'enabled', 0, NULL, '{}'::jsonb, FALSE),
    (23, 18, '登录删除', 'button', NULL, FALSE, 'monitor:logininfor:remove', NULL, NULL, 'enabled', 0, NULL, '{}'::jsonb, FALSE),
    (24, 18, '日志导出', 'button', NULL, FALSE, 'monitor:logininfor:export', NULL, NULL, 'enabled', 0, NULL, '{}'::jsonb, FALSE),
    (25, 18, '账户解锁', 'button', NULL, FALSE, 'monitor:logininfor:unlock', NULL, NULL, 'enabled', 0, NULL, '{}'::jsonb, FALSE)
ON CONFLICT (id) DO NOTHING;

SELECT setval('access_control_items_id_seq', (SELECT MAX(id) FROM access_control_items));
