"""日志管理接口的集成测试。"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.crud.logs import operation_log_crud
from app.models.log import OperationLog, OperationLogMonitorRule
from app.services.log_service import log_service


def _auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _insert_operation_log(db: Session, *, log_number: str) -> None:
    _ensure_monitor_rule(
        db,
        request_uri="/prod-api/system",
        http_method="ALL",
        match_mode="prefix",
        is_enabled=True,
    )

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


def _ensure_monitor_rule(
    db: Session,
    *,
    request_uri: str,
    http_method: str,
    match_mode: str,
    is_enabled: bool,
) -> OperationLogMonitorRule:
    existing = (
        db.query(OperationLogMonitorRule)
        .filter(
            OperationLogMonitorRule.request_uri == request_uri,
            OperationLogMonitorRule.http_method == http_method,
            OperationLogMonitorRule.match_mode == match_mode,
            OperationLogMonitorRule.is_deleted.is_(False),
        )
        .first()
    )
    if existing:
        if existing.is_enabled != is_enabled:
            existing.is_enabled = is_enabled
            db.add(existing)
            db.commit()
            db.refresh(existing)
        return existing

    rule = OperationLogMonitorRule(
        name="测试规则",
        request_uri=request_uri,
        http_method=http_method,
        match_mode=match_mode,
        is_enabled=is_enabled,
        description="测试自动生成的监听规则",
        operation_type_code="query",
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


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


def test_record_operation_log_skips_disabled_route(db_session_fixture: Session):
    _ensure_monitor_rule(
        db_session_fixture,
        request_uri="/api/v1/logs/operations",
        http_method="ALL",
        match_mode="prefix",
        is_enabled=False,
    )

    payload = {
        "module": "日志管理",
        "business_type": "query",
        "operator_name": "admin",
        "operator_department": None,
        "operator_ip": "127.0.0.1",
        "operator_location": None,
        "request_method": "GET",
        "request_uri": "/api/v1/logs/operations",
        "class_method": "tests.test_logs.test_record_operation_log_skips_disabled_route",
        "request_params": None,
        "response_params": None,
        "status": "success",
        "error_message": None,
        "cost_ms": 0,
        "operate_time": datetime.now(timezone.utc),
    }

    result = log_service.record_operation_log(db_session_fixture, payload=payload)
    assert result is None

    stored_count = (
        db_session_fixture.query(OperationLog)
        .filter(OperationLog.request_uri.like("/api/v1/logs/operations%"))
        .count()
    )
    assert stored_count == 0


def test_record_operation_log_requires_enabled_rule(db_session_fixture: Session):
    log_number = log_service.generate_operation_number(datetime(2027, 1, 1, 0, 0, 0, tzinfo=timezone.utc))
    payload = {
        "module": "未配置接口",
        "business_type": "query",
        "operator_name": "observer",
        "operator_department": None,
        "operator_ip": "192.168.0.1",
        "operator_location": None,
        "request_method": "GET",
        "request_uri": "/api/v1/untracked/resource",
        "class_method": "tests.test_logs.test_record_operation_log_requires_enabled_rule",
        "request_params": None,
        "response_params": None,
        "status": "success",
        "error_message": None,
        "cost_ms": 1,
        "operate_time": datetime.now(timezone.utc),
    }

    result = log_service.record_operation_log(db_session_fixture, payload=payload, log_number=log_number)
    assert result is None

    _ensure_monitor_rule(
        db_session_fixture,
        request_uri="/api/v1/untracked",
        http_method="ALL",
        match_mode="prefix",
        is_enabled=True,
    )

    second_number = log_service.generate_operation_number(datetime(2027, 1, 1, 0, 1, 0, tzinfo=timezone.utc))
    recorded = log_service.record_operation_log(
        db_session_fixture,
        payload=payload | {"operate_time": datetime(2027, 1, 1, 0, 1, 0, tzinfo=timezone.utc)},
        log_number=second_number,
    )
    assert recorded is not None
    assert recorded.request_uri == "/api/v1/untracked/resource"


def test_operation_log_listing_retains_records_after_rule_disabled(db_session_fixture: Session):
    _ensure_monitor_rule(
        db_session_fixture,
        request_uri="/api/v1/internal/diagnose",
        http_method="ALL",
        match_mode="prefix",
        is_enabled=True,
    )

    timestamp = datetime(2026, 1, 1, 8, 0, 0, tzinfo=timezone.utc)
    log_number = log_service.generate_operation_number(timestamp)
    recorded = log_service.record_operation_log(
        db_session_fixture,
        payload={
            "module": "内部接口",
            "business_type": "query",
            "operator_name": "tester",
            "operator_department": None,
            "operator_ip": "10.0.0.1",
            "operator_location": None,
            "request_method": "POST",
            "request_uri": "/api/v1/internal/diagnose/ping",
            "class_method": "tests.test_logs.test_operation_log_listing_retains_records_after_rule_disabled",
            "request_params": None,
            "response_params": None,
            "status": "success",
            "error_message": None,
            "cost_ms": 12,
            "operate_time": timestamp,
        },
        log_number=log_number,
    )

    assert recorded is not None

    _ensure_monitor_rule(
        db_session_fixture,
        request_uri="/api/v1/internal/diagnose",
        http_method="ALL",
        match_mode="prefix",
        is_enabled=False,
    )

    skipped_number = log_service.generate_operation_number(datetime(2026, 1, 1, 8, 5, 0, tzinfo=timezone.utc))
    skipped = log_service.record_operation_log(
        db_session_fixture,
        payload={
            "module": "内部接口",
            "business_type": "query",
            "operator_name": "tester",
            "operator_department": None,
            "operator_ip": "10.0.0.1",
            "operator_location": None,
            "request_method": "POST",
            "request_uri": "/api/v1/internal/diagnose/ping",
            "class_method": "tests.test_logs.test_operation_log_listing_retains_records_after_rule_disabled",
            "request_params": None,
            "response_params": None,
            "status": "success",
            "error_message": None,
            "cost_ms": 8,
            "operate_time": datetime(2026, 1, 1, 8, 5, 0, tzinfo=timezone.utc),
        },
        log_number=skipped_number,
    )

    assert skipped is None

    persisted = (
        db_session_fixture.query(OperationLog)
        .filter(OperationLog.log_number == log_number)
        .one_or_none()
    )
    assert persisted is not None

    items, total = operation_log_crud.list_with_filters(db_session_fixture, limit=200)
    assert total >= 1
    assert any(item.log_number == log_number for item in items)


def test_monitor_rule_crud_flow(client: TestClient, db_session_fixture: Session):
    headers = _auth_headers(client)

    create_payload = {
        "name": "测试规则",
        "request_uri": "/api/v1/sensitive",
        "http_method": "post",
        "match_mode": "prefix",
        "is_enabled": True,
        "description": "仅用于单元测试",
        "operation_type_code": "query",
    }

    create_resp = client.post(
        "/api/v1/logs/monitor-rules",
        json=create_payload,
        headers=headers,
    )
    assert create_resp.status_code == 201
    created = create_resp.json()["data"]
    rule_id = created["id"]
    assert created["http_method"] == "POST"
    assert created["operation_type_label"] == "查询"

    detail_resp = client.get(f"/api/v1/logs/monitor-rules/{rule_id}", headers=headers)
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()["data"]
    assert detail_data["id"] == rule_id

    update_resp = client.put(
        f"/api/v1/logs/monitor-rules/{rule_id}",
        json={"is_enabled": False},
        headers=headers,
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()["data"]
    assert updated["is_enabled"] is False
    assert updated["operation_type_label"] == "查询"

    list_resp = client.get(
        "/api/v1/logs/monitor-rules",
        params={"request_uri": "sensitive", "page_size": 5},
        headers=headers,
    )
    assert list_resp.status_code == 200
    list_data = list_resp.json()["data"]
    assert list_data["total"] >= 1
    assert any(item["id"] == rule_id for item in list_data["items"])

    delete_resp = client.delete(f"/api/v1/logs/monitor-rules/{rule_id}", headers=headers)
    assert delete_resp.status_code == 200

    absent_resp = client.get(f"/api/v1/logs/monitor-rules/{rule_id}", headers=headers)
    assert absent_resp.status_code == 404

    conflict_resp = client.post(
        "/api/v1/logs/monitor-rules",
        json={
            "request_uri": "/api/v1/logs/operations",
            "http_method": "ALL",
            "match_mode": "prefix",
        },
        headers=headers,
    )
    assert conflict_resp.status_code == 409
