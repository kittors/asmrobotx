-- ---------------------------------------------------------------------------
-- 数据初始化脚本
-- 说明：预置操作日志监听规则、组织/角色/权限、字典数据及菜单权限。
--      请在结构初始化 (01_init.sql) 执行完成后再运行本脚本。
-- ---------------------------------------------------------------------------

-- 默认禁用日志接口自身的监听，避免递归记录。
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
      AND is_deleted = FALSE
);

-- 认证模块 API 监听规则
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
    v.name,
    v.request_uri,
    v.http_method,
    v.match_mode,
    v.is_enabled,
    v.description,
    v.operation_type_code
FROM (VALUES
    ('认证-用户注册', '/api/v1/auth/register', 'POST', 'exact', TRUE, '注册新用户', 'create'),
    ('认证-用户登录', '/api/v1/auth/login', 'POST', 'exact', FALSE, '用户登录获取令牌', 'other'),
    ('认证-退出登录', '/api/v1/auth/logout', 'POST', 'exact', FALSE, '退出当前会话', 'other')
) AS v(name, request_uri, http_method, match_mode, is_enabled, description, operation_type_code)
WHERE NOT EXISTS (
    SELECT 1
    FROM operation_log_monitor_rules existing
    WHERE existing.request_uri = v.request_uri
      AND existing.http_method = v.http_method
      AND existing.match_mode = v.match_mode
      AND existing.is_deleted = FALSE
);

-- 组织模块 API 监听规则
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
    v.name,
    v.request_uri,
    v.http_method,
    v.match_mode,
    v.is_enabled,
    v.description,
    v.operation_type_code
FROM (VALUES
    ('组织-列表查询', '/api/v1/organizations', 'GET', 'exact', TRUE, '获取组织机构列表', 'query')
) AS v(name, request_uri, http_method, match_mode, is_enabled, description, operation_type_code)
WHERE NOT EXISTS (
    SELECT 1
    FROM operation_log_monitor_rules existing
    WHERE existing.request_uri = v.request_uri
      AND existing.http_method = v.http_method
      AND existing.match_mode = v.match_mode
      AND existing.is_deleted = FALSE
);

-- 访问控制模块 API 监听规则
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
    v.name,
    v.request_uri,
    v.http_method,
    v.match_mode,
    v.is_enabled,
    v.description,
    v.operation_type_code
FROM (VALUES
    ('访问控制-树查询', '/api/v1/access-controls', 'GET', 'exact', TRUE, '查询访问控制树', 'query'),
    ('访问控制-路由获取', '/api/v1/access-controls/routers', 'GET', 'exact', TRUE, '获取动态路由配置', 'query'),
    ('访问控制-详情查询', '/api/v1/access-controls/', 'GET', 'prefix', TRUE, '获取访问控制项详情', 'query'),
    ('访问控制-新增', '/api/v1/access-controls', 'POST', 'exact', TRUE, '新增访问控制项', 'create'),
    ('访问控制-更新', '/api/v1/access-controls/', 'PUT', 'prefix', TRUE, '更新访问控制项', 'update'),
    ('访问控制-删除', '/api/v1/access-controls/', 'DELETE', 'prefix', TRUE, '删除访问控制项', 'delete')
) AS v(name, request_uri, http_method, match_mode, is_enabled, description, operation_type_code)
WHERE NOT EXISTS (
    SELECT 1
    FROM operation_log_monitor_rules existing
    WHERE existing.request_uri = v.request_uri
      AND existing.http_method = v.http_method
      AND existing.match_mode = v.match_mode
      AND existing.is_deleted = FALSE
);

-- 角色管理模块 API 监听规则
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
    v.name,
    v.request_uri,
    v.http_method,
    v.match_mode,
    v.is_enabled,
    v.description,
    v.operation_type_code
FROM (VALUES
    ('角色-列表查询', '/api/v1/roles', 'GET', 'exact', TRUE, '分页查询角色列表', 'query'),
    ('角色-详情查询', '/api/v1/roles/', 'GET', 'prefix', TRUE, '获取角色详情', 'query'),
    ('角色-新增', '/api/v1/roles', 'POST', 'exact', TRUE, '新增角色', 'create'),
    ('角色-更新', '/api/v1/roles/', 'PUT', 'prefix', TRUE, '更新角色信息', 'update'),
    ('角色-状态切换', '/api/v1/roles/', 'PATCH', 'prefix', TRUE, '更新角色状态', 'update'),
    ('角色-删除', '/api/v1/roles/', 'DELETE', 'prefix', TRUE, '删除角色', 'delete'),
    ('角色-导出', '/api/v1/roles/export', 'GET', 'exact', TRUE, '导出角色列表', 'export')
) AS v(name, request_uri, http_method, match_mode, is_enabled, description, operation_type_code)
WHERE NOT EXISTS (
    SELECT 1
    FROM operation_log_monitor_rules existing
    WHERE existing.request_uri = v.request_uri
      AND existing.http_method = v.http_method
      AND existing.match_mode = v.match_mode
      AND existing.is_deleted = FALSE
);

-- 用户管理模块 API 监听规则
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
    v.name,
    v.request_uri,
    v.http_method,
    v.match_mode,
    v.is_enabled,
    v.description,
    v.operation_type_code
FROM (VALUES
    ('用户-当前信息', '/api/v1/users/me', 'GET', 'exact', TRUE, '获取当前用户信息', 'query'),
    ('用户-列表查询', '/api/v1/users', 'GET', 'exact', TRUE, '分页查询用户列表', 'query'),
    ('用户-新增', '/api/v1/users', 'POST', 'exact', TRUE, '新增用户', 'create'),
    ('用户-更新', '/api/v1/users/', 'PUT', 'prefix', TRUE, '更新用户信息或重置密码', 'update'),
    ('用户-删除', '/api/v1/users/', 'DELETE', 'prefix', TRUE, '删除用户', 'delete'),
    ('用户-导出', '/api/v1/users/export', 'GET', 'exact', TRUE, '导出用户列表', 'export'),
    ('用户-导入', '/api/v1/users/import', 'POST', 'exact', TRUE, '导入用户数据', 'import'),
    ('用户-模板下载', '/api/v1/users/template', 'GET', 'exact', TRUE, '下载用户导入模板', 'export')
) AS v(name, request_uri, http_method, match_mode, is_enabled, description, operation_type_code)
WHERE NOT EXISTS (
    SELECT 1
    FROM operation_log_monitor_rules existing
    WHERE existing.request_uri = v.request_uri
      AND existing.http_method = v.http_method
      AND existing.match_mode = v.match_mode
      AND existing.is_deleted = FALSE
);

-- 字典管理模块 API 监听规则
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
    v.name,
    v.request_uri,
    v.http_method,
    v.match_mode,
    v.is_enabled,
    v.description,
    v.operation_type_code
FROM (VALUES
    ('字典类型-列表查询', '/api/v1/dictionary_types', 'GET', 'exact', TRUE, '获取字典类型列表', 'query'),
    ('字典类型-新增', '/api/v1/dictionary_types', 'POST', 'exact', TRUE, '新增字典类型', 'create'),
    ('字典类型-更新', '/api/v1/dictionary_types/', 'PUT', 'prefix', TRUE, '更新字典类型', 'update'),
    ('字典类型-删除', '/api/v1/dictionary_types/', 'DELETE', 'prefix', TRUE, '删除字典类型', 'delete'),
    ('字典项-列表查询', '/api/v1/dictionaries/', 'GET', 'prefix', TRUE, '分页查询字典项', 'query'),
    ('字典项-新增', '/api/v1/dictionaries', 'POST', 'exact', TRUE, '新增字典项', 'create'),
    ('字典项-更新', '/api/v1/dictionaries/', 'PUT', 'prefix', TRUE, '更新字典项', 'update'),
    ('字典项-删除', '/api/v1/dictionaries/', 'DELETE', 'prefix', TRUE, '删除字典项', 'delete')
) AS v(name, request_uri, http_method, match_mode, is_enabled, description, operation_type_code)
WHERE NOT EXISTS (
    SELECT 1
    FROM operation_log_monitor_rules existing
    WHERE existing.request_uri = v.request_uri
      AND existing.http_method = v.http_method
      AND existing.match_mode = v.match_mode
      AND existing.is_deleted = FALSE
);

-- 日志管理模块 API 监听规则
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
    v.name,
    v.request_uri,
    v.http_method,
    v.match_mode,
    v.is_enabled,
    v.description,
    v.operation_type_code
FROM (VALUES
    ('日志-操作日志列表', '/api/v1/logs/operations', 'GET', 'exact', FALSE, '查询操作日志列表', 'query'),
    ('日志-操作日志详情', '/api/v1/logs/operations/', 'GET', 'prefix', FALSE, '获取操作日志详情', 'query'),
    ('日志-操作日志删除', '/api/v1/logs/operations/', 'DELETE', 'prefix', FALSE, '删除单条操作日志', 'delete'),
    ('日志-操作日志清除', '/api/v1/logs/operations', 'DELETE', 'exact', FALSE, '清除全部操作日志', 'clean'),
    ('日志-操作日志导出', '/api/v1/logs/operations/export', 'GET', 'exact', FALSE, '导出操作日志', 'export'),
    ('日志-登录日志列表', '/api/v1/logs/logins', 'GET', 'exact', TRUE, '查询登录日志列表', 'query'),
    ('日志-登录日志删除', '/api/v1/logs/logins/', 'DELETE', 'prefix', TRUE, '删除登录日志', 'delete'),
    ('日志-登录日志清除', '/api/v1/logs/logins', 'DELETE', 'exact', TRUE, '清除全部登录日志', 'clean'),
    ('日志-监听规则列表', '/api/v1/logs/monitor-rules', 'GET', 'exact', TRUE, '查询监听规则列表', 'query'),
    ('日志-监听规则新增', '/api/v1/logs/monitor-rules', 'POST', 'exact', TRUE, '新增监听规则', 'create'),
    ('日志-监听规则详情', '/api/v1/logs/monitor-rules/', 'GET', 'prefix', TRUE, '获取监听规则详情', 'query'),
    ('日志-监听规则更新', '/api/v1/logs/monitor-rules/', 'PUT', 'prefix', TRUE, '更新监听规则', 'update'),
    ('日志-监听规则删除', '/api/v1/logs/monitor-rules/', 'DELETE', 'prefix', TRUE, '删除监听规则', 'delete')
) AS v(name, request_uri, http_method, match_mode, is_enabled, description, operation_type_code)
WHERE NOT EXISTS (
    SELECT 1
    FROM operation_log_monitor_rules existing
    WHERE existing.request_uri = v.request_uri
      AND existing.http_method = v.http_method
      AND existing.match_mode = v.match_mode
      AND existing.is_deleted = FALSE
);

-- 组织与角色等基础数据
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

-- 字典类型
INSERT INTO dictionary_types (type_code, display_name, description, sort_order)
VALUES
    ('display_status', '显示状态', '用于表示菜单或组件在前端的显示控制', 1),
    ('enabled_status', '启用状态', '用于标记资源当前是否可用', 2),
    ('icon_list', '图标列表', '为前端图标选择器提供可用图标', 3),
    ('operation_log_type', '操作日志类型', '区分操作日志的业务动作', 4)
ON CONFLICT (type_code) DO NOTHING;

-- 字典条目：图标、状态等基础配置
INSERT INTO dictionary_entries (type_code, label, value, description, sort_order)
VALUES
    ('display_status', '显示', 'show', '用于表示菜单或组件应在前端展示', 1),
    ('display_status', '隐藏', 'hidden', '用于表示菜单或组件应在前端隐藏', 2)
ON CONFLICT (type_code, value) DO NOTHING;

INSERT INTO dictionary_entries (type_code, label, value, description, sort_order)
VALUES
    ('enabled_status', '启用', 'enabled', '标记条目当前处于启用状态', 1),
    ('enabled_status', '停用', 'disabled', '标记条目当前处于停用状态', 2)
ON CONFLICT (type_code, value) DO NOTHING;

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

-- 访问控制菜单及按钮权限
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
    (27, 1, '字典管理', 'menu', 'settings', FALSE, 'system:dictionary:list', 'dictionary', 'show', 'enabled', 0, 'system/dictionary/index', '{}'::jsonb, FALSE),
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

-- 访问控制主键自增序列对齐
SELECT setval('access_control_items_id_seq', (SELECT MAX(id) FROM access_control_items));

