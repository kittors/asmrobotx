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

    # 创建根目录
    create_dir_resp = client.post(
        "/api/v1/access-controls",
        headers=headers,
        json={
            "name": "系统管理",
            "type": "directory",
            "permission_code": "system:manage",
            "route_path": "/system",
            "display_status": "show",
            "enabled_status": "enabled",
            "icon": "icon-settings",
            "sort_order": 1,
        },
    )
    assert create_dir_resp.status_code == 200
    dir_payload = create_dir_resp.json()
    assert dir_payload["code"] == 200
    dir_id = dir_payload["data"]["id"]

    # 创建子菜单
    create_menu_resp = client.post(
        "/api/v1/access-controls",
        headers=headers,
        json={
            "parent_id": dir_id,
            "name": "菜单管理",
            "type": "menu",
            "permission_code": "system:menu:list",
            "route_path": "/system/menu",
            "display_status": "show",
            "enabled_status": "enabled",
            "icon": "icon-dashboard",
            "sort_order": 2,
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
    assert any(node["id"] == dir_id for node in tree_data)

    # 更新子菜单状态为停用
    update_resp = client.put(
        f"/api/v1/access-controls/{menu_id}",
        headers=headers,
        json={
            "name": "菜单管理",
            "permission_code": "system:menu:list",
            "route_path": "/system/menu/index",
            "display_status": "show",
            "enabled_status": "disabled",
            "icon": "icon-dashboard",
            "sort_order": 5,
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

    # 有子项的目录不允许删除
    client.post(
        "/api/v1/access-controls",
        headers=headers,
        json={
            "parent_id": dir_id,
            "name": "按钮A",
            "type": "button",
            "permission_code": "system:button:a",
            "enabled_status": "enabled",
            "sort_order": 1,
        },
    )
    delete_dir_resp = client.delete(f"/api/v1/access-controls/{dir_id}", headers=headers)
    assert delete_dir_resp.status_code == 400
    assert delete_dir_resp.json()["msg"] == "该项包含子项，无法删除"

    # 清理按钮后删除目录
    tree_resp = client.get("/api/v1/access-controls", headers=headers)
    button_id = next(
        child["id"]
        for node in tree_resp.json()["data"]
        for child in node.get("children", [])
        if child["permission_code"] == "system:button:a"
    )
    client.delete(f"/api/v1/access-controls/{button_id}", headers=headers)

    final_delete_resp = client.delete(f"/api/v1/access-controls/{dir_id}", headers=headers)
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


def test_access_control_reorder_flow(client: TestClient):
    """验证拖拽排序接口的行为，包括同级与跨级移动。"""
    token = _get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    # 创建两个根目录
    dir_a = client.post(
        "/api/v1/access-controls",
        headers=headers,
        json={
            "name": "目录A",
            "type": "directory",
            "permission_code": "ac:dir:a",
            "route_path": "/a",
            "display_status": "show",
            "enabled_status": "enabled",
        },
    ).json()["data"]
    dir_b = client.post(
        "/api/v1/access-controls",
        headers=headers,
        json={
            "name": "目录B",
            "type": "directory",
            "permission_code": "ac:dir:b",
            "route_path": "/b",
            "display_status": "show",
            "enabled_status": "enabled",
        },
    ).json()["data"]

    # 在目录 A 下创建两个菜单和一个按钮
    menu_a1 = client.post(
        "/api/v1/access-controls",
        headers=headers,
        json={
            "parent_id": dir_a["id"],
            "name": "菜单A1",
            "type": "menu",
            "permission_code": "ac:menu:a1",
            "route_path": "/a/menu1",
            "display_status": "show",
            "enabled_status": "enabled",
        },
    ).json()["data"]
    menu_a2 = client.post(
        "/api/v1/access-controls",
        headers=headers,
        json={
            "parent_id": dir_a["id"],
            "name": "菜单A2",
            "type": "menu",
            "permission_code": "ac:menu:a2",
            "route_path": "/a/menu2",
            "display_status": "show",
            "enabled_status": "enabled",
        },
    ).json()["data"]
    button_a = client.post(
        "/api/v1/access-controls",
        headers=headers,
        json={
            "parent_id": dir_a["id"],
            "name": "按钮A",
            "type": "button",
            "permission_code": "ac:button:a",
            "enabled_status": "enabled",
        },
    ).json()["data"]

    # 将菜单A2移动到同级首位
    reorder_same_parent = client.patch(
        f"/api/v1/access-controls/{menu_a2['id']}/reorder",
        headers=headers,
        json={"target_parent_id": dir_a["id"], "target_index": 0},
    )
    assert reorder_same_parent.status_code == 200
    assert reorder_same_parent.json()["data"]["sort_order"] == 0

    # 将按钮移动到菜单A1下
    reorder_to_child = client.patch(
        f"/api/v1/access-controls/{button_a['id']}/reorder",
        headers=headers,
        json={"target_parent_id": menu_a1["id"], "target_index": 0},
    )
    assert reorder_to_child.status_code == 200
    assert reorder_to_child.json()["data"]["parent_id"] == menu_a1["id"]

    # 将菜单A1移动到目录B下，作为其子菜单
    reorder_cross_parent = client.patch(
        f"/api/v1/access-controls/{menu_a1['id']}/reorder",
        headers=headers,
        json={"target_parent_id": dir_b["id"], "target_index": 0},
    )
    assert reorder_cross_parent.status_code == 200
    assert reorder_cross_parent.json()["data"]["parent_id"] == dir_b["id"]

    # 尝试非法操作：将目录移动到菜单下，期望 400
    invalid_move_directory = client.patch(
        f"/api/v1/access-controls/{dir_b['id']}/reorder",
        headers=headers,
        json={"target_parent_id": menu_a1["id"], "target_index": 0},
    )
    assert invalid_move_directory.status_code == 400
    assert invalid_move_directory.json()["msg"] == "目录类型仅能存在于顶层"

    # 尝试非法操作：将菜单移动到按钮下，期望 400
    invalid_move_to_button = client.patch(
        f"/api/v1/access-controls/{menu_a2['id']}/reorder",
        headers=headers,
        json={"target_parent_id": button_a["id"], "target_index": 0},
    )
    assert invalid_move_to_button.status_code == 400
    assert invalid_move_to_button.json()["msg"] == "按钮类型不允许拥有下级节点"
