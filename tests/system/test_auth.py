"""认证接口的集成测试用例。"""

from fastapi.testclient import TestClient


def test_register_user_success(client: TestClient):
    """注册流程：应成功创建新用户并返回基础信息。"""
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "tester", "password": "tester123"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["msg"] == "注册成功"
    assert payload["data"]["username"] == "tester"


def test_register_user_duplicate_username(client: TestClient):
    """注册流程：重复用户名时应返回 409 冲突。"""
    client.post(
        "/api/v1/auth/register",
        json={"username": "duplicate", "password": "tester123"},
    )
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "duplicate", "password": "tester123"},
    )

    assert response.status_code == 409
    payload = response.json()
    assert payload["code"] == 409
    assert payload["msg"] == "用户名已存在"


def test_login_success(client: TestClient):
    """登录流程：正确凭证应返回访问令牌。"""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin123"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["data"]["token_type"] == "bearer"
    assert payload["data"]["access_token"]


def test_login_invalid_credentials(client: TestClient):
    """登录流程：错误密码应提示认证失败。"""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "wrongpassword"},
    )
    assert response.status_code == 401
    payload = response.json()
    assert payload["code"] == 401
    assert payload["msg"] == "用户名或密码错误"


def test_logout_success(client: TestClient):
    """退出登录：有效令牌应返回成功消息。"""
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    token = login_resp.json()["data"]["access_token"]

    response = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["msg"] == "退出登录成功"
