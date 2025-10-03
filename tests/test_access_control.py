"""访问控制与字典接口的集成测试。"""

from fastapi.testclient import TestClient


def _get_token(client: TestClient) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    data = response.json()["data"]
    return data["access_token"]


def test_access_control_crud_flow(client: TestClient):
    """验证访问控制项的新增、查询、更新与删除流程。"""
    token = _get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    # 创建根菜单
    create_root_resp = client.post(
        "/api/v1/access-controls",
        headers=headers,
        json={
            "name": "系统管理",
            "type": "menu",
            "display_status": "show",
            "enabled_status": "enabled",
            "icon": "icon-settings",
            "sort_order": 1,
            "route_params": {"redirect": "/system/menu"},
            "keep_alive": True,
        },
    )
    assert create_root_resp.status_code == 200
    root_payload = create_root_resp.json()
    assert root_payload["code"] == 200
    root_menu_id = root_payload["data"]["id"]
    assert root_payload["data"]["route_path"] is None
    assert root_payload["data"]["component_path"] is None
    refreshed_token = create_root_resp.headers.get("X-Access-Token")
    assert refreshed_token
    assert root_payload.get("meta", {}).get("access_token") == refreshed_token

    # 创建子菜单
    create_menu_resp = client.post(
        "/api/v1/access-controls",
        headers=headers,
        json={
            "parent_id": root_menu_id,
            "name": "菜单管理",
            "type": "menu",
            "permission_code": "system:menu:list",
            "route_path": "/system/menu",
            "display_status": "show",
            "enabled_status": "enabled",
            "icon": "icon-dashboard",
            "sort_order": 2,
            "component_path": "views/system/menu/index.vue",
            "route_params": {"title": "菜单管理"},
            "keep_alive": False,
        },
    )
    assert create_menu_resp.status_code == 200
    menu_payload = create_menu_resp.json()
    assert menu_payload["code"] == 200
    menu_id = menu_payload["data"]["id"]

    # 列表查询应包含创建的节点
    list_resp = client.get("/api/v1/access-controls", headers=headers)
    assert list_resp.status_code == 200
    tree_data = list_resp.json()["data"]
    assert any(node["id"] == root_menu_id for node in tree_data)

    # 更新子菜单状态为停用
    update_resp = client.put(
        f"/api/v1/access-controls/{menu_id}",
        headers=headers,
        json={
            "name": "菜单管理",
            "route_path": "/system/menu/index",
            "display_status": "show",
            "enabled_status": "disabled",
            "icon": "icon-dashboard",
            "sort_order": 5,
            "component_path": "views/system/menu/index.vue",
            "route_params": {"title": "菜单管理"},
            "keep_alive": True,
        },
    )
    assert update_resp.status_code == 200
    update_payload = update_resp.json()["data"]
    assert update_payload["enabled_status"] == "disabled"

    # 筛选停用状态应包含该菜单
    filtered_resp = client.get(
        "/api/v1/access-controls",
        headers=headers,
        params={"enabled_status": "disabled"},
    )
    assert filtered_resp.status_code == 200
    filtered_tree = filtered_resp.json()["data"]
    assert filtered_tree
    assert any(
        child["id"] == menu_id and child["effective_enabled_status"] == "disabled"
        for node in filtered_tree
        for child in node.get("children", [])
    )

    # 删除子菜单
    delete_menu_resp = client.delete(f"/api/v1/access-controls/{menu_id}", headers=headers)
    assert delete_menu_resp.status_code == 200
    assert delete_menu_resp.json()["msg"] == "删除访问控制项成功"

    # 有子项的菜单不允许删除
    client.post(
        "/api/v1/access-controls",
        headers=headers,
        json={
            "parent_id": root_menu_id,
            "name": "按钮A",
            "type": "button",
            "permission_code": "system:button:a",
            "enabled_status": "enabled",
            "sort_order": 1,
        },
    )
    delete_root_resp = client.delete(f"/api/v1/access-controls/{root_menu_id}", headers=headers)
    assert delete_root_resp.status_code == 400
    assert delete_root_resp.json()["msg"] == "该项包含子项，无法删除"

    # 清理按钮后删除目录
    tree_resp = client.get("/api/v1/access-controls", headers=headers)
    button_id = next(
        child["id"]
        for node in tree_resp.json()["data"]
        for child in node.get("children", [])
        if child["permission_code"] == "system:button:a"
    )
    client.delete(f"/api/v1/access-controls/{button_id}", headers=headers)

    final_delete_resp = client.delete(f"/api/v1/access-controls/{root_menu_id}", headers=headers)
    assert final_delete_resp.status_code == 200
    assert final_delete_resp.json()["msg"] == "删除访问控制项成功"


def test_dictionary_endpoint_returns_seed_items(client: TestClient):
    """字典接口应返回初始化的字典条目。"""
    token = _get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/api/v1/dictionaries/display_status", headers=headers)
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["code"] == 200
    values = {item["value"] for item in payload["data"]}
    assert {"show", "hidden"}.issubset(values)
