"""角色分配（用户/数据权限）接口测试。"""

from fastapi.testclient import TestClient
import uuid


def _auth_headers(client: TestClient) -> dict[str, str]:
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    token = resp.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_assign_users_to_role(client: TestClient):
    headers = _auth_headers(client)

    # 创建一个新角色
    role_resp = client.post(
        "/api/v1/roles",
        headers=headers,
        json={
            "name": "测试角色A_RA_" + uuid.uuid4().hex[:6],
            "role_key": "test_role_a_" + uuid.uuid4().hex[:6],
            "sort_order": 1,
            "status": "normal",
            "permission_ids": [],
        },
    )
    role_id = role_resp.json()["data"]["role_id"]

    # 创建两个新用户
    u1 = client.post(
        "/api/v1/users",
        headers=headers,
        json={"username": "ra_user1", "password": "pass1234", "role_ids": [], "organization_id": 1},
    ).json()["data"]["user_id"]
    u2 = client.post(
        "/api/v1/users",
        headers=headers,
        json={"username": "ra_user2", "password": "pass1234", "role_ids": [], "organization_id": 1},
    ).json()["data"]["user_id"]

    # 初始查询：应为空
    empty_resp = client.get(f"/api/v1/roles/{role_id}/users", headers=headers)
    assert empty_resp.status_code == 200
    assert empty_resp.json()["data"]["user_ids"] == []

    # 分配两个用户
    assign_resp = client.put(
        f"/api/v1/roles/{role_id}/users",
        headers=headers,
        json={"user_ids": [u1, u2]},
    )
    assert assign_resp.status_code == 200
    assert sorted(assign_resp.json()["data"]["user_ids"]) == sorted([u1, u2])

    # 再次查询校验
    list_resp = client.get(f"/api/v1/roles/{role_id}/users", headers=headers)
    assert sorted(list_resp.json()["data"]["user_ids"]) == sorted([u1, u2])

    # 覆盖为单个用户
    reassign_resp = client.put(
        f"/api/v1/roles/{role_id}/users",
        headers=headers,
        json={"user_ids": [u2]},
    )
    assert reassign_resp.status_code == 200
    assert reassign_resp.json()["data"]["user_ids"] == [u2]


def test_assign_organizations_to_role(client: TestClient):
    headers = _auth_headers(client)

    # 准备一个新角色
    role_resp = client.post(
        "/api/v1/roles",
        headers=headers,
        json={
            "name": "测试角色B_RA_" + uuid.uuid4().hex[:6],
            "role_key": "test_role_b_" + uuid.uuid4().hex[:6],
            "sort_order": 1,
            "status": "normal",
            "permission_ids": [],
        },
    )
    role_id = role_resp.json()["data"]["role_id"]

    # 获取组织列表，选取前两个
    org_resp = client.get("/api/v1/organizations", headers=headers)
    org_items = org_resp.json()["data"]
    org_ids = [item["org_id"] for item in org_items[:2]] if len(org_items) >= 2 else [org_items[0]["org_id"]]

    # 初始为空
    empty_resp = client.get(f"/api/v1/roles/{role_id}/organizations", headers=headers)
    assert empty_resp.status_code == 200
    assert empty_resp.json()["data"]["organization_ids"] == []

    # 分配组织
    assign_resp = client.put(
        f"/api/v1/roles/{role_id}/organizations",
        headers=headers,
        json={"organization_ids": org_ids},
    )
    assert assign_resp.status_code == 200
    assert sorted(assign_resp.json()["data"]["organization_ids"]) == sorted(org_ids)

    # 查询校验
    list_resp = client.get(f"/api/v1/roles/{role_id}/organizations", headers=headers)
    assert sorted(list_resp.json()["data"]["organization_ids"]) == sorted(org_ids)
