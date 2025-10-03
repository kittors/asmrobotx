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
    organization_id INTEGER REFERENCES organizations(id),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    create_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS user_roles (
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    role_id INTEGER REFERENCES roles(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_id)
);

CREATE TABLE IF NOT EXISTS role_permissions (
    role_id INTEGER REFERENCES roles(id) ON DELETE CASCADE,
    permission_id INTEGER REFERENCES permissions(id) ON DELETE CASCADE,
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

INSERT INTO organizations (name)
VALUES ('研发部')
ON CONFLICT (name) DO NOTHING;

INSERT INTO roles (name) VALUES ('admin') ON CONFLICT (name) DO NOTHING;
INSERT INTO roles (name) VALUES ('user') ON CONFLICT (name) DO NOTHING;

INSERT INTO permissions (name, description, type)
VALUES
    ('view_dashboard', '查看仪表盘', 'route'),
    ('edit_self_profile', '编辑个人资料', 'route'),
    ('manage_users', '管理用户', 'route')
ON CONFLICT (name) DO NOTHING;

INSERT INTO users (username, hashed_password, organization_id, is_active)
VALUES (
    'admin',
    crypt('admin123', gen_salt('bf')),
    (SELECT id FROM organizations WHERE name = '研发部'),
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
