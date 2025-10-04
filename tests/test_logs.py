"""日志管理接口的集成测试。"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.log_service import log_service


def _auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _insert_operation_log(db: Session, *, log_number: str) -> None:
    payload = {
        "module": "服务记录管理",
        "business_type": "update",
        "operator_name": "admin",
        "operator_department": "管理层",
        "operator_ip": "183.161.76.183",
        "operator_location": "中国|安徽省|蚌埠市|电信",
        "request_method": "PUT",
        "request_uri": "/prod-api/system/serviceRecord",
        "class_method": "org.dromara.system.controller.system.ServiceRecordController.update()",
        "request_params": json.dumps(
            {
                "id": 70785,
                "name": "胡留荣",
            },
            ensure_ascii=False,
        ),
        "response_params": json.dumps({"code": 200, "msg": "操作成功", "data": None}, ensure_ascii=False),
        "status": "success",
        "cost_ms": 42,
        "operate_time": datetime(2025, 9, 30, 16, 5, 26, tzinfo=timezone.utc),
    }
    log_service.record_operation_log(db, payload=payload, log_number=log_number)


def _insert_login_log(db: Session, *, visit_number: str, username: str = "admin") -> None:
    payload = {
        "username": username,
        "client_name": "web",
        "device_type": "Chrome",
        "ip_address": "127.0.0.1",
        "login_location": "中国|安徽省|合肥市",
        "operating_system": "macOS",
        "browser": "Chrome",
        "status": "success",
        "message": "登录成功",
        "login_time": datetime(2025, 10, 3, 21, 8, 48, tzinfo=timezone.utc),
    }
    log_service.record_login_log(db, payload=payload, visit_number=visit_number)


def test_operation_logs_listing_and_detail(client: TestClient, db_session_fixture: Session):
    log_number = log_service.generate_operation_number(datetime(2025, 9, 30, 16, 5, 26, tzinfo=timezone.utc))
    _insert_operation_log(db_session_fixture, log_number=log_number)

    headers = _auth_headers(client)
    response = client.get("/api/v1/logs/operations", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert data["data"]["total"] >= 1
    items = data["data"]["items"]
    assert any(item["log_number"] == log_number for item in items)
    target_item = next(item for item in items if item["log_number"] == log_number)
    assert target_item["request_uri"] == "/prod-api/system/serviceRecord"

    detail = client.get(f"/api/v1/logs/operations/{log_number}", headers=headers)
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["code"] == 200
    assert detail_payload["data"]["log_number"] == log_number
    assert detail_payload["data"]["operation_module"]["operation_type"] == "修改"
    assert "request_params" in detail_payload["data"]


def test_operation_log_delete_and_clear(client: TestClient, db_session_fixture: Session):
    first_number = log_service.generate_operation_number(datetime(2025, 9, 30, 16, 6, 0, tzinfo=timezone.utc))
    second_number = log_service.generate_operation_number(datetime(2025, 9, 30, 16, 7, 0, tzinfo=timezone.utc))
    _insert_operation_log(db_session_fixture, log_number=first_number)
    _insert_operation_log(db_session_fixture, log_number=second_number)

    headers = _auth_headers(client)

    delete_resp = client.delete(f"/api/v1/logs/operations/{first_number}", headers=headers)
    assert delete_resp.status_code == 200
    assert delete_resp.json()["code"] == 200

    list_resp = client.get("/api/v1/logs/operations", headers=headers)
    assert all(item["log_number"] != first_number for item in list_resp.json()["data"]["items"])

    clear_resp = client.delete("/api/v1/logs/operations", headers=headers)
    assert clear_resp.status_code == 200
    assert clear_resp.json()["code"] == 200

    after_clear = client.get("/api/v1/logs/operations", headers=headers)
    remaining_items = after_clear.json()["data"]["items"]
    assert all(item["log_number"] != second_number for item in remaining_items)


def test_operation_logs_export(client: TestClient, db_session_fixture: Session):
    log_number = log_service.generate_operation_number(datetime(2025, 9, 30, 16, 8, 0, tzinfo=timezone.utc))
    _insert_operation_log(db_session_fixture, log_number=log_number)
    headers = _auth_headers(client)

    export_resp = client.get("/api/v1/logs/operations/export", headers=headers)
    assert export_resp.status_code == 200
    assert export_resp.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert export_resp.headers["content-disposition"].startswith("attachment; filename=")
    assert len(export_resp.content) > 0


def test_login_logs_listing_and_delete(client: TestClient, db_session_fixture: Session):
    visit_number = log_service.generate_visit_number(datetime(2025, 10, 3, 21, 8, 48, tzinfo=timezone.utc))
    _insert_login_log(db_session_fixture, visit_number=visit_number)

    headers = _auth_headers(client)
    response = client.get("/api/v1/logs/logins", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["data"]["total"] >= 1
    assert any(item["visit_number"] == visit_number for item in payload["data"]["items"])

    delete_resp = client.delete(f"/api/v1/logs/logins/{visit_number}", headers=headers)
    assert delete_resp.status_code == 200
    assert delete_resp.json()["code"] == 200

    clear_resp = client.delete("/api/v1/logs/logins", headers=headers)
    assert clear_resp.status_code == 200
    assert clear_resp.json()["code"] == 200
