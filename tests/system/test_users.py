"""用户接口的集成测试用例。"""

import io
import uuid

from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.packages.system.models.role import Role


def _get_token(client: TestClient) -> str:
    """获取管理员访问令牌的辅助方法。"""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    return response.json()["data"]["access_token"]


def _auth_headers(client: TestClient) -> dict[str, str]:
    token = _get_token(client)
    return {"Authorization": f"Bearer {token}"}


def test_get_current_user_success(client: TestClient):
    """应成功返回管理员的个人信息。"""
    token = _get_token(client)
    response = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["data"]["username"] == "admin"
    assert "admin" in payload["data"]["roles"]


def test_get_current_user_unauthorized(client: TestClient):
    """未提供令牌时应返回 401。"""
    response = client.get("/api/v1/users/me")
    assert response.status_code == 401
    payload = response.json()
    assert payload["code"] == 401
    assert payload["msg"] == "缺少认证信息"


def test_user_crud_flow(client: TestClient, db_session_fixture: Session):
    """验证用户新增、更新、重置密码及删除完整流程。"""

    headers = _auth_headers(client)
    role = db_session_fixture.query(Role).filter(Role.name == "user").first()
    assert role is not None

    username = f"tester_{uuid.uuid4().hex[:8]}"
    create_response = client.post(
        "/api/v1/users",
        json={
            "username": username,
            "password": "secret123",
            "nickname": "测试用户",
            "status": "normal",
            "role_ids": [role.id],
            "remark": "初始创建",
        },
        headers=headers,
    )

    assert create_response.status_code == 200
    payload = create_response.json()
    assert payload["code"] == 200
    user_id = payload["data"]["user_id"]
    assert payload["data"]["status"] == "normal"
    assert payload["data"]["role_ids"] == [role.id]

    list_response = client.get(
        "/api/v1/users",
        params={"username": username},
        headers=headers,
    )
    assert list_response.status_code == 200
    list_payload = list_response.json()["data"]
    assert list_payload["total"] == 1
    assert list_payload["items"][0]["username"] == username

    update_response = client.put(
        f"/api/v1/users/{user_id}",
        json={
            "nickname": "更新后的昵称",
            "status": "disabled",
            "role_ids": [],
            "remark": "已更新",
        },
        headers=headers,
    )
    assert update_response.status_code == 200
    update_payload = update_response.json()
    assert update_payload["data"]["status"] == "disabled"
    assert update_payload["data"]["role_ids"] == []

    reset_response = client.put(
        f"/api/v1/users/{user_id}/reset-password",
        json={"password": "newpass123"},
        headers=headers,
    )
    assert reset_response.status_code == 200
    assert reset_response.json()["data"]["user_id"] == user_id

    delete_response = client.delete(f"/api/v1/users/{user_id}", headers=headers)
    assert delete_response.status_code == 200
    assert delete_response.json()["data"]["user_id"] == user_id

    list_after_delete = client.get(
        "/api/v1/users",
        params={"username": username},
        headers=headers,
    )
    assert list_after_delete.status_code == 200
    assert list_after_delete.json()["data"]["total"] == 0


def test_export_and_template_download(client: TestClient):
    """应能够导出用户列表并下载导入模版。"""

    headers = _auth_headers(client)
    export_response = client.get("/api/v1/users/export", headers=headers)
    assert export_response.status_code == 200
    content_disposition = export_response.headers.get("content-disposition")
    assert content_disposition is not None and "attachment" in content_disposition

    template_response = client.get("/api/v1/users/template", headers=headers)
    assert template_response.status_code == 200
    template_disposition = template_response.headers.get("content-disposition")
    assert template_disposition is not None and "user-template.xlsx" in template_disposition


def test_import_users(client: TestClient, db_session_fixture: Session):
    """应支持根据模版批量导入用户。"""

    headers = _auth_headers(client)
    role = db_session_fixture.query(Role).filter(Role.name == "user").first()
    assert role is not None

    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["用户名", "密码", "用户昵称", "状态", "角色", "备注"])
    imported_username = f"import_{uuid.uuid4().hex[:8]}"
    sheet.append([
        imported_username,
        "import123",
        "导入用户",
        "normal",
        str(role.id),
        "通过导入创建",
    ])

    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)

    response = client.post(
        "/api/v1/users/import",
        files={"file": ("users.xlsx", buffer.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["created"] == 1
    assert payload["data"]["failed"] == []

    # 清理导入的用户，避免影响其他用例
    list_response = client.get(
        "/api/v1/users",
        params={"username": imported_username},
        headers=headers,
    )
    user_items = list_response.json()["data"]["items"]
    if user_items:
        client.delete(f"/api/v1/users/{user_items[0]['user_id']}", headers=headers)
