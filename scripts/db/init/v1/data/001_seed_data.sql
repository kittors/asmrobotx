-- ---------------------------------------------------------------------------
-- 数据初始化脚本
-- 说明：预置操作日志监听规则、组织/角色/权限、字典数据及菜单权限。
--      说明：请在结构初始化 (v1/schema) 完成后再运行。本仓库通过聚合入口
--            scripts/db/init/01_v1.sql 自动按“结构 -> 数据”的顺序执行，无需手工排序。
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

-- 访问控制模块 API 监听规则（使用路径模板）
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
    ('访问控制-路由获取', '/api/v1/access-controls/routers', 'GET', 'exact', FALSE, '获取动态路由配置', 'query'),
    ('访问控制-详情查询', '/api/v1/access-controls/{item_id}', 'GET', 'exact', TRUE, '获取访问控制项详情', 'query'),
    ('访问控制-新增', '/api/v1/access-controls', 'POST', 'exact', TRUE, '新增访问控制项', 'create'),
    ('访问控制-更新', '/api/v1/access-controls/{item_id}', 'PUT', 'exact', TRUE, '更新访问控制项', 'update'),
    ('访问控制-删除', '/api/v1/access-controls/{item_id}', 'DELETE', 'exact', TRUE, '删除访问控制项', 'delete')
) AS v(name, request_uri, http_method, match_mode, is_enabled, description, operation_type_code)
WHERE NOT EXISTS (
    SELECT 1
    FROM operation_log_monitor_rules existing
    WHERE existing.request_uri = v.request_uri
      AND existing.http_method = v.http_method
      AND existing.match_mode = v.match_mode
      AND existing.is_deleted = FALSE
);

-- 角色管理模块 API 监听规则（使用路径模板）
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
    ('角色-详情查询', '/api/v1/roles/{role_id}', 'GET', 'exact', TRUE, '获取角色详情', 'query'),
    ('角色-新增', '/api/v1/roles', 'POST', 'exact', TRUE, '新增角色', 'create'),
    ('角色-更新', '/api/v1/roles/{role_id}', 'PUT', 'exact', TRUE, '更新角色信息', 'update'),
    ('角色-状态切换', '/api/v1/roles/{role_id}/status', 'PATCH', 'exact', TRUE, '更新角色状态', 'update'),
    ('角色-删除', '/api/v1/roles/{role_id}', 'DELETE', 'exact', TRUE, '删除角色', 'delete'),
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

-- 用户管理模块 API 监听规则（使用路径模板）
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
    ('用户-更新', '/api/v1/users/{user_id}', 'PUT', 'exact', TRUE, '更新用户信息', 'update'),
    ('用户-删除', '/api/v1/users/{user_id}', 'DELETE', 'exact', TRUE, '删除用户', 'delete'),
    ('用户-重置密码', '/api/v1/users/{user_id}/reset-password', 'PUT', 'exact', TRUE, '重置用户密码', 'update'),
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

-- 字典管理模块 API 监听规则（使用路径模板）
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
    ('字典类型-更新', '/api/v1/dictionary_types/{type_code}', 'PUT', 'exact', TRUE, '更新字典类型', 'update'),
    ('字典类型-删除', '/api/v1/dictionary_types/{type_code}', 'DELETE', 'exact', TRUE, '删除字典类型', 'delete'),
    ('字典项-列表查询', '/api/v1/dictionaries/{type_code}', 'GET', 'exact', TRUE, '分页查询字典项', 'query'),
    ('字典项-新增', '/api/v1/dictionaries', 'POST', 'exact', TRUE, '新增字典项', 'create'),
    ('字典项-更新', '/api/v1/dictionaries/{id}', 'PUT', 'exact', TRUE, '更新字典项', 'update'),
    ('字典项-删除', '/api/v1/dictionaries/{id}', 'DELETE', 'exact', TRUE, '删除字典项', 'delete')
) AS v(name, request_uri, http_method, match_mode, is_enabled, description, operation_type_code)
WHERE NOT EXISTS (
    SELECT 1
    FROM operation_log_monitor_rules existing
    WHERE existing.request_uri = v.request_uri
      AND existing.http_method = v.http_method
      AND existing.match_mode = v.match_mode
      AND existing.is_deleted = FALSE
);

-- 日志管理模块 API 监听规则（对自身接口默认禁用；使用路径模板）
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
    ('日志-操作日志详情', '/api/v1/logs/operations/{log_number}', 'GET', 'exact', FALSE, '获取操作日志详情', 'query'),
    ('日志-操作日志删除', '/api/v1/logs/operations/{log_number}', 'DELETE', 'exact', FALSE, '删除单条操作日志', 'delete'),
    ('日志-操作日志清除', '/api/v1/logs/operations', 'DELETE', 'exact', FALSE, '清除全部操作日志', 'clean'),
    ('日志-操作日志导出', '/api/v1/logs/operations/export', 'GET', 'exact', FALSE, '导出操作日志', 'export'),
    ('日志-登录日志列表', '/api/v1/logs/logins', 'GET', 'exact', TRUE, '查询登录日志列表', 'query'),
    ('日志-登录日志删除', '/api/v1/logs/logins/{visit_number}', 'DELETE', 'exact', TRUE, '删除登录日志', 'delete'),
    ('日志-登录日志清除', '/api/v1/logs/logins', 'DELETE', 'exact', TRUE, '清除全部登录日志', 'clean'),
    ('日志-监听规则列表', '/api/v1/logs/monitor-rules', 'GET', 'exact', TRUE, '查询监听规则列表', 'query'),
    ('日志-监听规则新增', '/api/v1/logs/monitor-rules', 'POST', 'exact', TRUE, '新增监听规则', 'create'),
    ('日志-监听规则详情', '/api/v1/logs/monitor-rules/{rule_id}', 'GET', 'exact', TRUE, '获取监听规则详情', 'query'),
    ('日志-监听规则更新', '/api/v1/logs/monitor-rules/{rule_id}', 'PUT', 'exact', TRUE, '更新监听规则', 'update'),
    ('日志-监听规则删除', '/api/v1/logs/monitor-rules/{rule_id}', 'DELETE', 'exact', TRUE, '删除监听规则', 'delete')
) AS v(name, request_uri, http_method, match_mode, is_enabled, description, operation_type_code)
WHERE NOT EXISTS (
    SELECT 1
    FROM operation_log_monitor_rules existing
    WHERE existing.request_uri = v.request_uri
      AND existing.http_method = v.http_method
      AND existing.match_mode = v.match_mode
      AND existing.is_deleted = FALSE
);

-- ---------------------------------------------------------------------------
-- 文件管理模块 API 监听规则（与 docs/system/api/file_manager.md 对齐）
-- ---------------------------------------------------------------------------
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
    -- 存储源管理
    ('存储-列表', '/api/v1/storage-configs', 'GET', 'exact', TRUE, '查询存储源列表', 'query'),
    ('存储-详情', '/api/v1/storage-configs/{config_id}', 'GET', 'exact', TRUE, '获取存储源详情', 'query'),
    ('存储-新增', '/api/v1/storage-configs', 'POST', 'exact', TRUE, '新增存储源', 'create'),
    ('存储-更新', '/api/v1/storage-configs/{config_id}', 'PUT', 'exact', TRUE, '更新存储源', 'update'),
    ('存储-删除', '/api/v1/storage-configs/{config_id}', 'DELETE', 'exact', TRUE, '删除存储源配置', 'delete'),
    ('存储-连通性测试', '/api/v1/storage-configs/test', 'POST', 'exact', TRUE, '测试存储源连通性', 'query'),

    -- 文件与目录
    ('文件-列表', '/api/v1/files', 'GET', 'exact', TRUE, '列出目录内容', 'query'),
    ('文件-上传', '/api/v1/files', 'POST', 'exact', TRUE, '上传文件', 'create'),
    ('文件-下载', '/api/v1/files/download', 'GET', 'exact', TRUE, '下载文件', 'query'),
    ('文件-预览', '/api/v1/files/preview', 'GET', 'exact', TRUE, '预览文件', 'query'),
    ('目录-创建', '/api/v1/folders', 'POST', 'exact', TRUE, '创建文件夹', 'create'),
    ('文件-重命名', '/api/v1/files', 'PATCH', 'exact', TRUE, '重命名文件或文件夹', 'update'),
    ('文件-移动', '/api/v1/files/move', 'POST', 'exact', TRUE, '移动文件或文件夹', 'update'),
    ('文件-复制', '/api/v1/files/copy', 'POST', 'exact', TRUE, '复制文件或文件夹', 'create'),
    ('文件-删除', '/api/v1/files', 'DELETE', 'exact', TRUE, '删除文件或文件夹', 'delete'),

    -- 剪贴板
    ('剪贴板-设置', '/api/v1/files/clipboard', 'POST', 'exact', TRUE, '设置剪贴板', 'other'),
    ('剪贴板-获取', '/api/v1/files/clipboard', 'GET', 'exact', TRUE, '获取剪贴板', 'query'),
    ('剪贴板-清空', '/api/v1/files/clipboard', 'DELETE', 'exact', TRUE, '清空剪贴板', 'other'),
    ('剪贴板-粘贴', '/api/v1/files/paste', 'POST', 'exact', TRUE, '在目标目录执行粘贴', 'update')
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
    -- 优先常用图标（按 sort_order 提前到最前）
    ('icon_list', '工具箱', 'tool-case', '工具图标', 1),
    ('icon_list', '设置', 'settings', '设置图标', 2),
    ('icon_list', '搜索', 'search', '通用搜索图标', 3),
    ('icon_list', '外链', 'link', '外链/跳转图标', 4),
    ('icon_list', '地图定位', 'map-pinned', '地理定位图标', 5),
    ('icon_list', '菜单', 'menu', '菜单/列表图标', 6),
    ('icon_list', '向下箭头', 'a-arrow-down', 'Lucide图标：向下箭头', 7),
    ('icon_list', '向上箭头', 'a-arrow-up', 'Lucide图标：向上箭头', 8),
    ('icon_list', '一大一小', 'a-large-small', 'Lucide图标：一大一小', 9),
    ('icon_list', '无障碍', 'accessibility', 'Lucide图标：无障碍', 10),
    ('icon_list', '活动', 'activity', 'Lucide图标：活动', 11),
    ('icon_list', '通风口', 'air-vent', 'Lucide图标：通风口', 12),
    ('icon_list', '空中播放', 'airplay', 'Lucide图标：空中播放', 13),
    ('icon_list', '闹钟', 'alarm-clock', 'Lucide图标：闹钟', 14),
    ('icon_list', '闹钟检查', 'alarm-clock-check', 'Lucide图标：闹钟检查', 15),
    ('icon_list', '闹钟减号', 'alarm-clock-minus', 'Lucide图标：闹钟减号', 16),
    ('icon_list', '闹钟关闭', 'alarm-clock-off', 'Lucide图标：闹钟关闭', 17),
    ('icon_list', '闹钟加', 'alarm-clock-plus', 'Lucide图标：闹钟加', 18),
    ('icon_list', '报警烟雾', 'alarm-smoke', 'Lucide图标：报警烟雾', 19),
    ('icon_list', '专辑', 'album', 'Lucide图标：专辑', 20),
    ('icon_list', '居中对齐', 'align-center', 'Lucide图标：居中对齐', 21),
    ('icon_list', '水平居中对齐', 'align-center-horizontal', 'Lucide图标：水平居中对齐', 22),
    ('icon_list', '垂直居中对齐', 'align-center-vertical', 'Lucide图标：垂直居中对齐', 23),
    ('icon_list', '水平对齐端部', 'align-end-horizontal', 'Lucide图标：水平对齐端部', 24),
    ('icon_list', '垂直对齐端部', 'align-end-vertical', 'Lucide图标：垂直对齐端部', 25),
    ('icon_list', '水平分布中心对齐', 'align-horizontal-distribute-center', 'Lucide图标：水平分布中心对齐', 26),
    ('icon_list', '对齐水平分布端', 'align-horizontal-distribute-end', 'Lucide图标：对齐水平分布端', 27),
    ('icon_list', '水平对齐分布起点', 'align-horizontal-distribute-start', 'Lucide图标：水平对齐分布起点', 28),
    ('icon_list', '水平居中对齐', 'align-horizontal-justify-center', 'Lucide图标：水平居中对齐', 29),
    ('icon_list', '水平对齐 两端对齐', 'align-horizontal-justify-end', 'Lucide图标：水平对齐 两端对齐', 30),
    ('icon_list', '水平对齐 对齐开始', 'align-horizontal-justify-start', 'Lucide图标：水平对齐 对齐开始', 31),
    ('icon_list', '对齐周围的水平空间', 'align-horizontal-space-around', 'Lucide图标：对齐周围的水平空间', 32),
    ('icon_list', '对齐之间的水平空间', 'align-horizontal-space-between', 'Lucide图标：对齐之间的水平空间', 33),
    ('icon_list', '对齐对齐', 'align-justify', 'Lucide图标：对齐对齐', 34),
    ('icon_list', '左对齐', 'align-left', 'Lucide图标：左对齐', 35),
    ('icon_list', '右对齐', 'align-right', 'Lucide图标：右对齐', 36),
    ('icon_list', '水平起始对齐', 'align-start-horizontal', 'Lucide图标：水平起始对齐', 37),
    ('icon_list', '垂直起始对齐', 'align-start-vertical', 'Lucide图标：垂直起始对齐', 38),
    ('icon_list', '垂直分布中心对齐', 'align-vertical-distribute-center', 'Lucide图标：垂直分布中心对齐', 39),
    ('icon_list', '对齐垂直分布端', 'align-vertical-distribute-end', 'Lucide图标：对齐垂直分布端', 40),
    ('icon_list', '对齐垂直分布起点', 'align-vertical-distribute-start', 'Lucide图标：对齐垂直分布起点', 41),
    ('icon_list', '垂直居中对齐', 'align-vertical-justify-center', 'Lucide图标：垂直居中对齐', 42),
    ('icon_list', '垂直对齐端对齐', 'align-vertical-justify-end', 'Lucide图标：垂直对齐端对齐', 43),
    ('icon_list', '垂直对齐 开始对齐', 'align-vertical-justify-start', 'Lucide图标：垂直对齐 开始对齐', 44),
    ('icon_list', '对齐周围的垂直空间', 'align-vertical-space-around', 'Lucide图标：对齐周围的垂直空间', 45),
    ('icon_list', '对齐之间的垂直空间', 'align-vertical-space-between', 'Lucide图标：对齐之间的垂直空间', 46),
    ('icon_list', '救护车', 'ambulance', 'Lucide图标：救护车', 47),
    ('icon_list', '和号', 'ampersand', 'Lucide图标：和号', 48),
    ('icon_list', '& 符号', 'ampersands', 'Lucide图标：& 符号', 49),
    ('icon_list', '双耳瓶', 'amphora', 'Lucide图标：双耳瓶', 50),
    ('icon_list', '锚', 'anchor', 'Lucide图标：锚', 51),
    ('icon_list', '生气的', 'angry', 'Lucide图标：生气的', 52),
    ('icon_list', '生气', 'annoyed', 'Lucide图标：生气', 53),
    ('icon_list', '天线', 'antenna', 'Lucide图标：天线', 54),
    ('icon_list', '砧', 'anvil', 'Lucide图标：砧', 55),
    ('icon_list', '光圈', 'aperture', 'Lucide图标：光圈', 56),
    ('icon_list', '应用程序窗口', 'app-window', 'Lucide图标：应用程序窗口', 57),
    ('icon_list', '应用程序窗口 Mac', 'app-window-mac', 'Lucide图标：应用程序窗口 Mac', 58),
    ('icon_list', '苹果', 'apple', 'Lucide图标：苹果', 59),
    ('icon_list', '档案', 'archive', 'Lucide图标：档案', 60),
    ('icon_list', '存档恢复', 'archive-restore', 'Lucide图标：存档恢复', 61),
    ('icon_list', '档案X', 'archive-x', 'Lucide图标：档案X', 62),
    ('icon_list', '扶手椅', 'armchair', 'Lucide图标：扶手椅', 63),
    ('icon_list', '大向下箭头', 'arrow-big-down', 'Lucide图标：大向下箭头', 64),
    ('icon_list', '箭头大向下破折号', 'arrow-big-down-dash', 'Lucide图标：箭头大向下破折号', 65),
    ('icon_list', '大左箭头', 'arrow-big-left', 'Lucide图标：大左箭头', 66),
    ('icon_list', '箭头大左破折号', 'arrow-big-left-dash', 'Lucide图标：箭头大左破折号', 67),
    ('icon_list', '向右大箭头', 'arrow-big-right', 'Lucide图标：向右大箭头', 68),
    ('icon_list', '箭头大右破折号', 'arrow-big-right-dash', 'Lucide图标：箭头大右破折号', 69),
    ('icon_list', '向上箭头', 'arrow-big-up', 'Lucide图标：向上箭头', 70),
    ('icon_list', '箭头大向上冲刺', 'arrow-big-up-dash', 'Lucide图标：箭头大向上冲刺', 71),
    ('icon_list', '向下箭头', 'arrow-down', 'Lucide图标：向下箭头', 72),
    ('icon_list', '向下箭头 0 1', 'arrow-down-0-1', 'Lucide图标：向下箭头 0 1', 73),
    ('icon_list', '向下箭头 1 0', 'arrow-down-1-0', 'Lucide图标：向下箭头 1 0', 74),
    ('icon_list', '向下箭头 A Z', 'arrow-down-a-z', 'Lucide图标：向下箭头 A Z', 75),
    ('icon_list', '从线向下箭头', 'arrow-down-from-line', 'Lucide图标：从线向下箭头', 76),
    ('icon_list', '左下箭头', 'arrow-down-left', 'Lucide图标：左下箭头', 77),
    ('icon_list', '向下箭头 窄 宽', 'arrow-down-narrow-wide', 'Lucide图标：向下箭头 窄 宽', 78),
    ('icon_list', '右下箭头', 'arrow-down-right', 'Lucide图标：右下箭头', 79),
    ('icon_list', '向下箭头到点', 'arrow-down-to-dot', 'Lucide图标：向下箭头到点', 80),
    ('icon_list', '向下箭头至线', 'arrow-down-to-line', 'Lucide图标：向下箭头至线', 81),
    ('icon_list', '向下箭头向上', 'arrow-down-up', 'Lucide图标：向下箭头向上', 82),
    ('icon_list', '向下箭头 宽 窄', 'arrow-down-wide-narrow', 'Lucide图标：向下箭头 宽 窄', 83),
    ('icon_list', '向下箭头 Z A', 'arrow-down-z-a', 'Lucide图标：向下箭头 Z A', 84),
    ('icon_list', '向左箭头', 'arrow-left', 'Lucide图标：向左箭头', 85),
    ('icon_list', '从线向左箭头', 'arrow-left-from-line', 'Lucide图标：从线向左箭头', 86),
    ('icon_list', '箭头 左 右', 'arrow-left-right', 'Lucide图标：箭头 左 右', 87),
    ('icon_list', '向左箭头到线', 'arrow-left-to-line', 'Lucide图标：向左箭头到线', 88),
    ('icon_list', '向右箭头', 'arrow-right', 'Lucide图标：向右箭头', 89),
    ('icon_list', '线右箭头', 'arrow-right-from-line', 'Lucide图标：线右箭头', 90),
    ('icon_list', '箭头右左', 'arrow-right-left', 'Lucide图标：箭头右左', 91),
    ('icon_list', '向右箭头到线', 'arrow-right-to-line', 'Lucide图标：向右箭头到线', 92),
    ('icon_list', '向上箭头', 'arrow-up', 'Lucide图标：向上箭头', 93),
    ('icon_list', '向上箭头 0 1', 'arrow-up-0-1', 'Lucide图标：向上箭头 0 1', 94),
    ('icon_list', '向上箭头 1 0', 'arrow-up-1-0', 'Lucide图标：向上箭头 1 0', 95),
    ('icon_list', '向上箭头 A Z', 'arrow-up-a-z', 'Lucide图标：向上箭头 A Z', 96),
    ('icon_list', '向上箭头 向下箭头', 'arrow-up-down', 'Lucide图标：向上箭头 向下箭头', 97),
    ('icon_list', '从点向上箭头', 'arrow-up-from-dot', 'Lucide图标：从点向上箭头', 98),
    ('icon_list', '从线向上箭头', 'arrow-up-from-line', 'Lucide图标：从线向上箭头', 99),
    ('icon_list', '左上箭头', 'arrow-up-left', 'Lucide图标：左上箭头', 100),
    ('icon_list', '向上箭头 窄 宽', 'arrow-up-narrow-wide', 'Lucide图标：向上箭头 窄 宽', 101),
    ('icon_list', '右上箭头', 'arrow-up-right', 'Lucide图标：右上箭头', 102),
    ('icon_list', '向上箭头至行', 'arrow-up-to-line', 'Lucide图标：向上箭头至行', 103),
    ('icon_list', '箭头向上 宽 窄', 'arrow-up-wide-narrow', 'Lucide图标：箭头向上 宽 窄', 104),
    ('icon_list', '向上箭头 Z A', 'arrow-up-z-a', 'Lucide图标：向上箭头 Z A', 105),
    ('icon_list', '从线向上的箭头', 'arrows-up-from-line', 'Lucide图标：从线向上的箭头', 106),
    ('icon_list', '星号', 'asterisk', 'Lucide图标：星号', 107),
    ('icon_list', '在标志处', 'at-sign', 'Lucide图标：在标志处', 108),
    ('icon_list', '原子', 'atom', 'Lucide图标：原子', 109),
    ('icon_list', '音频线', 'audio-lines', 'Lucide图标：音频线', 110),
    ('icon_list', '音频波形', 'audio-waveform', 'Lucide图标：音频波形', 111),
    ('icon_list', '奖', 'award', 'Lucide图标：奖', 112),
    ('icon_list', '斧头', 'axe', 'Lucide图标：斧头', 113),
    ('icon_list', '轴 3d', 'axis-3d', 'Lucide图标：轴 3d', 114),
    ('icon_list', '婴儿', 'baby', 'Lucide图标：婴儿', 115),
    ('icon_list', '背包', 'backpack', 'Lucide图标：背包', 116),
    ('icon_list', '徽章', 'badge', 'Lucide图标：徽章', 117),
    ('icon_list', '徽章警报', 'badge-alert', 'Lucide图标：徽章警报', 118),
    ('icon_list', '徽章中心', 'badge-cent', 'Lucide图标：徽章中心', 119),
    ('icon_list', '徽章检查', 'badge-check', 'Lucide图标：徽章检查', 120),
    ('icon_list', '徽章美元符号', 'badge-dollar-sign', 'Lucide图标：徽章美元符号', 121),
    ('icon_list', '欧元徽章', 'badge-euro', 'Lucide图标：欧元徽章', 122),
    ('icon_list', '徽章印度卢比', 'badge-indian-rupee', 'Lucide图标：徽章印度卢比', 123),
    ('icon_list', '徽章信息', 'badge-info', 'Lucide图标：徽章信息', 124),
    ('icon_list', '徽章日元', 'badge-japanese-yen', 'Lucide图标：徽章日元', 125),
    ('icon_list', '徽章减号', 'badge-minus', 'Lucide图标：徽章减号', 126),
    ('icon_list', '徽章百分比', 'badge-percent', 'Lucide图标：徽章百分比', 127),
    ('icon_list', '徽章加号', 'badge-plus', 'Lucide图标：徽章加号', 128),
    ('icon_list', '徽章英镑', 'badge-pound-sterling', 'Lucide图标：徽章英镑', 129),
    ('icon_list', '徽章问号', 'badge-question-mark', 'Lucide图标：徽章问号', 130),
    ('icon_list', '徽章俄罗斯卢布', 'badge-russian-ruble', 'Lucide图标：徽章俄罗斯卢布', 131),
    ('icon_list', '徽章瑞士法郎', 'badge-swiss-franc', 'Lucide图标：徽章瑞士法郎', 132),
    ('icon_list', '徽章X', 'badge-x', 'Lucide图标：徽章X', 133),
    ('icon_list', '行李领取处', 'baggage-claim', 'Lucide图标：行李领取处', 134),
    ('icon_list', '禁止', 'ban', 'Lucide图标：禁止', 135),
    ('icon_list', '香蕉', 'banana', 'Lucide图标：香蕉', 136),
    ('icon_list', '绷带', 'bandage', 'Lucide图标：绷带', 137),
    ('icon_list', '钞票', 'banknote', 'Lucide图标：钞票', 138),
    ('icon_list', '钞票箭头向下', 'banknote-arrow-down', 'Lucide图标：钞票箭头向下', 139),
    ('icon_list', '钞票向上箭头', 'banknote-arrow-up', 'Lucide图标：钞票向上箭头', 140),
    ('icon_list', '钞票X', 'banknote-x', 'Lucide图标：钞票X', 141),
    ('icon_list', '条码', 'barcode', 'Lucide图标：条码', 142),
    ('icon_list', '桶', 'barrel', 'Lucide图标：桶', 143),
    ('icon_list', '基线', 'baseline', 'Lucide图标：基线', 144),
    ('icon_list', '洗澡', 'bath', 'Lucide图标：洗澡', 145),
    ('icon_list', '电池', 'battery', 'Lucide图标：电池', 146),
    ('icon_list', '电池充电', 'battery-charging', 'Lucide图标：电池充电', 147),
    ('icon_list', '电池充满', 'battery-full', 'Lucide图标：电池充满', 148),
    ('icon_list', '电池电量低', 'battery-low', 'Lucide图标：电池电量低', 149),
    ('icon_list', '电池介质', 'battery-medium', 'Lucide图标：电池介质', 150),
    ('icon_list', '电池加', 'battery-plus', 'Lucide图标：电池加', 151),
    ('icon_list', '电池警告', 'battery-warning', 'Lucide图标：电池警告', 152),
    ('icon_list', '烧杯', 'beaker', 'Lucide图标：烧杯', 153),
    ('icon_list', '豆', 'bean', 'Lucide图标：豆', 154),
    ('icon_list', '豆关', 'bean-off', 'Lucide图标：豆关', 155),
    ('icon_list', '床', 'bed', 'Lucide图标：床', 156),
    ('icon_list', '双人床', 'bed-double', 'Lucide图标：双人床', 157),
    ('icon_list', '单人床', 'bed-single', 'Lucide图标：单人床', 158),
    ('icon_list', '牛肉', 'beef', 'Lucide图标：牛肉', 159),
    ('icon_list', '啤酒', 'beer', 'Lucide图标：啤酒', 160),
    ('icon_list', '啤酒关', 'beer-off', 'Lucide图标：啤酒关', 161),
    ('icon_list', '钟', 'bell', 'Lucide图标：钟', 162),
    ('icon_list', '钟点', 'bell-dot', 'Lucide图标：钟点', 163),
    ('icon_list', '贝尔电气', 'bell-electric', 'Lucide图标：贝尔电气', 164),
    ('icon_list', '钟减', 'bell-minus', 'Lucide图标：钟减', 165),
    ('icon_list', '关门铃', 'bell-off', 'Lucide图标：关门铃', 166),
    ('icon_list', '贝尔加', 'bell-plus', 'Lucide图标：贝尔加', 167),
    ('icon_list', '铃声', 'bell-ring', 'Lucide图标：铃声', 168),
    ('icon_list', '水平端之间', 'between-horizontal-end', 'Lucide图标：水平端之间', 169),
    ('icon_list', '水平起点之间', 'between-horizontal-start', 'Lucide图标：水平起点之间', 170),
    ('icon_list', '垂直端之间', 'between-vertical-end', 'Lucide图标：垂直端之间', 171),
    ('icon_list', '垂直起点之间', 'between-vertical-start', 'Lucide图标：垂直起点之间', 172),
    ('icon_list', '二头肌弯曲', 'biceps-flexed', 'Lucide图标：二头肌弯曲', 173),
    ('icon_list', '自行车', 'bike', 'Lucide图标：自行车', 174),
    ('icon_list', '二进制', 'binary', 'Lucide图标：二进制', 175),
    ('icon_list', '双筒望远镜', 'binoculars', 'Lucide图标：双筒望远镜', 176),
    ('icon_list', '生化危机', 'biohazard', 'Lucide图标：生化危机', 177),
    ('icon_list', '鸟', 'bird', 'Lucide图标：鸟', 178),
    ('icon_list', '比特币', 'bitcoin', 'Lucide图标：比特币', 179),
    ('icon_list', '混合', 'blend', 'Lucide图标：混合', 180),
    ('icon_list', '百叶窗', 'blinds', 'Lucide图标：百叶窗', 181),
    ('icon_list', '积木', 'blocks', 'Lucide图标：积木', 182),
    ('icon_list', '蓝牙', 'bluetooth', 'Lucide图标：蓝牙', 183),
    ('icon_list', '蓝牙连接', 'bluetooth-connected', 'Lucide图标：蓝牙连接', 184),
    ('icon_list', '蓝牙关闭', 'bluetooth-off', 'Lucide图标：蓝牙关闭', 185),
    ('icon_list', '蓝牙搜索', 'bluetooth-searching', 'Lucide图标：蓝牙搜索', 186),
    ('icon_list', '大胆的', 'bold', 'Lucide图标：大胆的', 187),
    ('icon_list', '螺栓', 'bolt', 'Lucide图标：螺栓', 188),
    ('icon_list', '炸弹', 'bomb', 'Lucide图标：炸弹', 189),
    ('icon_list', '骨', 'bone', 'Lucide图标：骨', 190),
    ('icon_list', '书', 'book', 'Lucide图标：书', 191),
    ('icon_list', '书A', 'book-a', 'Lucide图标：书A', 192),
    ('icon_list', '预订提醒', 'book-alert', 'Lucide图标：预订提醒', 193),
    ('icon_list', '图书音频', 'book-audio', 'Lucide图标：图书音频', 194),
    ('icon_list', '预订支票', 'book-check', 'Lucide图标：预订支票', 195),
    ('icon_list', '书籍副本', 'book-copy', 'Lucide图标：书籍副本', 196),
    ('icon_list', '书破折号', 'book-dashed', 'Lucide图标：书破折号', 197),
    ('icon_list', '预订', 'book-down', 'Lucide图标：预订', 198),
    ('icon_list', '书本耳机', 'book-headphones', 'Lucide图标：书本耳机', 199),
    ('icon_list', '书心', 'book-heart', 'Lucide图标：书心', 200),
    ('icon_list', '书籍图片', 'book-image', 'Lucide图标：书籍图片', 201),
    ('icon_list', '书本钥匙', 'book-key', 'Lucide图标：书本钥匙', 202),
    ('icon_list', '书锁', 'book-lock', 'Lucide图标：书锁', 203),
    ('icon_list', '书标', 'book-marked', 'Lucide图标：书标', 204),
    ('icon_list', '书减', 'book-minus', 'Lucide图标：书减', 205),
    ('icon_list', '已开放预订', 'book-open', 'Lucide图标：已开放预订', 206),
    ('icon_list', '开书支票', 'book-open-check', 'Lucide图标：开书支票', 207),
    ('icon_list', '书本打开文本', 'book-open-text', 'Lucide图标：书本打开文本', 208),
    ('icon_list', '书加', 'book-plus', 'Lucide图标：书加', 209),
    ('icon_list', '书籍正文', 'book-text', 'Lucide图标：书籍正文', 210),
    ('icon_list', '书籍类型', 'book-type', 'Lucide图标：书籍类型', 211),
    ('icon_list', '预订', 'book-up', 'Lucide图标：预订', 212),
    ('icon_list', '预订 2', 'book-up-2', 'Lucide图标：预订 2', 213),
    ('icon_list', '预订用户', 'book-user', 'Lucide图标：预订用户', 214),
    ('icon_list', '第十册', 'book-x', 'Lucide图标：第十册', 215),
    ('icon_list', '书签', 'bookmark', 'Lucide图标：书签', 216),
    ('icon_list', '书签检查', 'bookmark-check', 'Lucide图标：书签检查', 217),
    ('icon_list', '书签减号', 'bookmark-minus', 'Lucide图标：书签减号', 218),
    ('icon_list', '书签加', 'bookmark-plus', 'Lucide图标：书签加', 219),
    ('icon_list', '书签X', 'bookmark-x', 'Lucide图标：书签X', 220),
    ('icon_list', '音箱', 'boom-box', 'Lucide图标：音箱', 221),
    ('icon_list', '机器人', 'bot', 'Lucide图标：机器人', 222),
    ('icon_list', '机器人消息广场', 'bot-message-square', 'Lucide图标：机器人消息广场', 223),
    ('icon_list', '机器人关闭', 'bot-off', 'Lucide图标：机器人关闭', 224),
    ('icon_list', '瓶装酒', 'bottle-wine', 'Lucide图标：瓶装酒', 225),
    ('icon_list', '弓箭', 'bow-arrow', 'Lucide图标：弓箭', 226),
    ('icon_list', '盒子', 'box', 'Lucide图标：盒子', 227),
    ('icon_list', '盒子', 'boxes', 'Lucide图标：盒子', 228),
    ('icon_list', '牙套', 'braces', 'Lucide图标：牙套', 229),
    ('icon_list', '括号', 'brackets', 'Lucide图标：括号', 230),
    ('icon_list', '脑', 'brain', 'Lucide图标：脑', 231),
    ('icon_list', '脑回路', 'brain-circuit', 'Lucide图标：脑回路', 232),
    ('icon_list', '大脑齿轮', 'brain-cog', 'Lucide图标：大脑齿轮', 233),
    ('icon_list', '砖墙', 'brick-wall', 'Lucide图标：砖墙', 234),
    ('icon_list', '砖墙火灾', 'brick-wall-fire', 'Lucide图标：砖墙火灾', 235),
    ('icon_list', '公文包', 'briefcase', 'Lucide图标：公文包', 236),
    ('icon_list', '公文包业务', 'briefcase-business', 'Lucide图标：公文包业务', 237),
    ('icon_list', '公文包传送带', 'briefcase-conveyor-belt', 'Lucide图标：公文包传送带', 238),
    ('icon_list', '公文包医疗', 'briefcase-medical', 'Lucide图标：公文包医疗', 239),
    ('icon_list', '带到前面', 'bring-to-front', 'Lucide图标：带到前面', 240),
    ('icon_list', '刷子', 'brush', 'Lucide图标：刷子', 241),
    ('icon_list', '刷子清洁', 'brush-cleaning', 'Lucide图标：刷子清洁', 242),
    ('icon_list', '气泡', 'bubbles', 'Lucide图标：气泡', 243),
    ('icon_list', '漏洞', 'bug', 'Lucide图标：漏洞', 244),
    ('icon_list', '关闭', 'bug-off', 'Lucide图标：关闭', 245),
    ('icon_list', '虫子游戏', 'bug-play', 'Lucide图标：虫子游戏', 246),
    ('icon_list', '建筑', 'building', 'Lucide图标：建筑', 247),
    ('icon_list', '2号楼', 'building-2', 'Lucide图标：2号楼', 248),
    ('icon_list', '公共汽车', 'bus', 'Lucide图标：公共汽车', 249),
    ('icon_list', '巴士前部', 'bus-front', 'Lucide图标：巴士前部', 250),
    ('icon_list', '电缆', 'cable', 'Lucide图标：电缆', 251),
    ('icon_list', '缆车', 'cable-car', 'Lucide图标：缆车', 252),
    ('icon_list', '蛋糕', 'cake', 'Lucide图标：蛋糕', 253),
    ('icon_list', '蛋糕片', 'cake-slice', 'Lucide图标：蛋糕片', 254),
    ('icon_list', '计算器', 'calculator', 'Lucide图标：计算器', 255),
    ('icon_list', '日历', 'calendar', 'Lucide图标：日历', 256),
    ('icon_list', '日历1', 'calendar-1', 'Lucide图标：日历1', 257),
    ('icon_list', '日历向下箭头', 'calendar-arrow-down', 'Lucide图标：日历向下箭头', 258),
    ('icon_list', '日历箭头向上', 'calendar-arrow-up', 'Lucide图标：日历箭头向上', 259),
    ('icon_list', '日历检查', 'calendar-check', 'Lucide图标：日历检查', 260),
    ('icon_list', '日历检查2', 'calendar-check-2', 'Lucide图标：日历检查2', 261),
    ('icon_list', '日历时钟', 'calendar-clock', 'Lucide图标：日历时钟', 262),
    ('icon_list', '日历齿轮', 'calendar-cog', 'Lucide图标：日历齿轮', 263),
    ('icon_list', '日历日', 'calendar-days', 'Lucide图标：日历日', 264),
    ('icon_list', '日历折叠', 'calendar-fold', 'Lucide图标：日历折叠', 265),
    ('icon_list', '日历心', 'calendar-heart', 'Lucide图标：日历心', 266),
    ('icon_list', '日历减号', 'calendar-minus', 'Lucide图标：日历减号', 267),
    ('icon_list', '日历减 2', 'calendar-minus-2', 'Lucide图标：日历减 2', 268),
    ('icon_list', '日历关闭', 'calendar-off', 'Lucide图标：日历关闭', 269),
    ('icon_list', '日历加', 'calendar-plus', 'Lucide图标：日历加', 270),
    ('icon_list', '日历加2', 'calendar-plus-2', 'Lucide图标：日历加2', 271),
    ('icon_list', '日历范围', 'calendar-range', 'Lucide图标：日历范围', 272),
    ('icon_list', '日历搜索', 'calendar-search', 'Lucide图标：日历搜索', 273),
    ('icon_list', '日历同步', 'calendar-sync', 'Lucide图标：日历同步', 274),
    ('icon_list', '日历 X', 'calendar-x', 'Lucide图标：日历 X', 275),
    ('icon_list', '日历×2', 'calendar-x-2', 'Lucide图标：日历×2', 276),
    ('icon_list', '相机', 'camera', 'Lucide图标：相机', 277),
    ('icon_list', '相机关闭', 'camera-off', 'Lucide图标：相机关闭', 278),
    ('icon_list', '糖果', 'candy', 'Lucide图标：糖果', 279),
    ('icon_list', '拐杖糖', 'candy-cane', 'Lucide图标：拐杖糖', 280),
    ('icon_list', '糖果关', 'candy-off', 'Lucide图标：糖果关', 281),
    ('icon_list', '大麻', 'cannabis', 'Lucide图标：大麻', 282),
    ('icon_list', '字幕', 'captions', 'Lucide图标：字幕', 283),
    ('icon_list', '字幕关闭', 'captions-off', 'Lucide图标：字幕关闭', 284),
    ('icon_list', '车', 'car', 'Lucide图标：车', 285),
    ('icon_list', '汽车前部', 'car-front', 'Lucide图标：汽车前部', 286),
    ('icon_list', '汽车出租车前面', 'car-taxi-front', 'Lucide图标：汽车出租车前面', 287),
    ('icon_list', '大篷车', 'caravan', 'Lucide图标：大篷车', 288),
    ('icon_list', '卡SIM卡', 'card-sim', 'Lucide图标：卡SIM卡', 289),
    ('icon_list', '胡萝卜', 'carrot', 'Lucide图标：胡萝卜', 290),
    ('icon_list', '下壳', 'case-lower', 'Lucide图标：下壳', 291),
    ('icon_list', '区分大小写', 'case-sensitive', 'Lucide图标：区分大小写', 292),
    ('icon_list', '外壳上部', 'case-upper', 'Lucide图标：外壳上部', 293),
    ('icon_list', '磁带', 'cassette-tape', 'Lucide图标：磁带', 294),
    ('icon_list', '投掷', 'cast', 'Lucide图标：投掷', 295),
    ('icon_list', '城堡', 'castle', 'Lucide图标：城堡', 296),
    ('icon_list', '猫', 'cat', 'Lucide图标：猫', 297),
    ('icon_list', '中央电视台', 'cctv', 'Lucide图标：中央电视台', 298),
    ('icon_list', '图表区', 'chart-area', 'Lucide图标：图表区', 299),
    ('icon_list', '图表栏', 'chart-bar', 'Lucide图标：图表栏', 300),
    ('icon_list', '图表栏大', 'chart-bar-big', 'Lucide图标：图表栏大', 301),
    ('icon_list', '图表栏减少', 'chart-bar-decreasing', 'Lucide图标：图表栏减少', 302),
    ('icon_list', '图表栏增加', 'chart-bar-increasing', 'Lucide图标：图表栏增加', 303),
    ('icon_list', '堆叠图表栏', 'chart-bar-stacked', 'Lucide图标：堆叠图表栏', 304),
    ('icon_list', '图表烛台', 'chart-candlestick', 'Lucide图标：图表烛台', 305),
    ('icon_list', '图表栏', 'chart-column', 'Lucide图标：图表栏', 306)
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
    (25, 18, '账户解锁', 'button', NULL, FALSE, 'monitor:logininfor:unlock', NULL, NULL, 'enabled', 0, NULL, '{}'::jsonb, FALSE),
    (28, 1, '文件管理', 'menu', 'settings', FALSE, 'system:fileManager:list', 'fileManager', 'show', 'enabled', 0, 'system/FileManager/index', '{}'::jsonb, FALSE)
ON CONFLICT (id) DO NOTHING;

-- 访问控制主键自增序列对齐
SELECT setval('access_control_items_id_seq', (SELECT MAX(id) FROM access_control_items));
