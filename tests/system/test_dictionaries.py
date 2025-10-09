"""系统字典管理模块的集成测试。"""

from fastapi.testclient import TestClient


def _get_token(client: TestClient) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    data = response.json()["data"]
    return data["access_token"]


def test_dictionary_type_and_item_management(client: TestClient):
    """验证字典类型与字典项的增删改查流程。"""
    token = _get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    create_type_resp = client.post(
        "/api/v1/dictionary_types",
        headers=headers,
        json={
            "type_code": "priority_level",
            "display_name": "优先级",
            "description": "用于控制任务处理优先顺序",
            "sort_order": 5,
        },
    )
    assert create_type_resp.status_code == 200
    type_payload = create_type_resp.json()
    assert type_payload["code"] == 200
    assert type_payload["data"]["type_code"] == "priority_level"

    list_type_resp = client.get(
        "/api/v1/dictionary_types",
        headers=headers,
        params={"keyword": "priority"},
    )
    assert list_type_resp.status_code == 200
    list_payload = list_type_resp.json()
    assert any(item["type_code"] == "priority_level" for item in list_payload["data"])

    update_type_resp = client.put(
        "/api/v1/dictionary_types/priority_level",
        headers=headers,
        json={
            "display_name": "优先级配置",
            "description": "更新后的描述信息",
            "sort_order": 7,
        },
    )
    assert update_type_resp.status_code == 200
    update_type_payload = update_type_resp.json()
    assert update_type_payload["data"]["display_name"] == "优先级配置"
    assert update_type_payload["data"]["sort_order"] == 7

    create_item_resp = client.post(
        "/api/v1/dictionaries",
        headers=headers,
        json={
            "type_code": "priority_level",
            "label": "高优先级",
            "value": "high",
            "description": "立即处理",
            "sort_order": 1,
        },
    )
    assert create_item_resp.status_code == 200
    item_payload = create_item_resp.json()
    item_id = item_payload["data"]["id"]

    create_item_resp_2 = client.post(
        "/api/v1/dictionaries",
        headers=headers,
        json={
            "type_code": "priority_level",
            "label": "低优先级",
            "value": "low",
            "sort_order": 3,
        },
    )
    assert create_item_resp_2.status_code == 200
    item_payload_2 = create_item_resp_2.json()
    item_id_2 = item_payload_2["data"]["id"]

    list_items_resp = client.get(
        "/api/v1/dictionaries/priority_level",
        headers=headers,
        params={"page": 1, "size": 10},
    )
    assert list_items_resp.status_code == 200
    items_payload = list_items_resp.json()["data"]
    assert items_payload["total"] >= 2
    values = {entry["value"] for entry in items_payload["list"]}
    assert {"high", "low"}.issubset(values)

    update_item_resp = client.put(
        f"/api/v1/dictionaries/{item_id}",
        headers=headers,
        json={
            "label": "高优先级",
            "value": "high",
            "description": "需要优先调度",
            "sort_order": 2,
        },
    )
    assert update_item_resp.status_code == 200
    updated_item = update_item_resp.json()["data"]
    assert updated_item["sort_order"] == 2
    assert updated_item["description"] == "需要优先调度"

    delete_item_resp = client.delete(f"/api/v1/dictionaries/{item_id_2}", headers=headers)
    assert delete_item_resp.status_code == 200
    delete_item_payload = delete_item_resp.json()
    assert delete_item_payload["data"]["id"] == item_id_2

    delete_type_resp = client.delete("/api/v1/dictionary_types/priority_level", headers=headers)
    assert delete_type_resp.status_code == 200
    delete_type_payload = delete_type_resp.json()
    assert delete_type_payload["data"]["type_code"] == "priority_level"
    assert delete_type_payload["data"]["deleted_items"] == 1

    # 删除后再次查询应返回 404
    deleted_list_resp = client.get("/api/v1/dictionaries/priority_level", headers=headers)
    assert deleted_list_resp.status_code == 404
    assert deleted_list_resp.json()["msg"] == "字典类型不存在或已删除"


def test_dictionary_item_value_conflict(client: TestClient):
    """同一类型下字典项的值应保持唯一。"""
    token = _get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    client.post(
        "/api/v1/dictionary_types",
        headers=headers,
        json={
            "type_code": "status_level",
            "display_name": "状态级别",
        },
    )

    first_resp = client.post(
        "/api/v1/dictionaries",
        headers=headers,
        json={
            "type_code": "status_level",
            "label": "正常",
            "value": "normal",
        },
    )
    assert first_resp.status_code == 200

    conflict_resp = client.post(
        "/api/v1/dictionaries",
        headers=headers,
        json={
            "type_code": "status_level",
            "label": "正常2",
            "value": "normal",
        },
    )
    assert conflict_resp.status_code == 409
    conflict_payload = conflict_resp.json()
    assert conflict_payload["msg"] == "字典值在该类型下已存在"
