"""组织接口的集成测试用例。"""

from fastapi.testclient import TestClient


def test_get_organizations(client: TestClient):
    """应成功返回包含默认组织的列表。"""
    response = client.get("/api/v1/organizations")

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["msg"] == "获取组织机构列表成功"
    assert isinstance(payload["data"], list)
    assert any(org["org_name"] == "研发部" for org in payload["data"])
