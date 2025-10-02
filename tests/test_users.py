"""用户接口的集成测试用例。"""

from fastapi.testclient import TestClient


def _get_token(client: TestClient) -> str:
    """获取管理员访问令牌的辅助方法。"""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    return response.json()["data"]["access_token"]


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
