"""监听规则模板匹配（{param}）的测试用例。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.packages.system.models.log import OperationLog, OperationLogMonitorRule
from app.packages.system.services.log_service import log_service


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
        name="模板匹配-测试规则",
        request_uri=request_uri,
        http_method=http_method,
        match_mode=match_mode,
        is_enabled=is_enabled,
        description="单元测试：模板匹配",
        operation_type_code="query",
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def test_template_exact_matches_single_segment(db_session_fixture: Session):
    # 规则采用模板形式，精确匹配（按 path 维度）。
    _ensure_monitor_rule(
        db_session_fixture,
        request_uri="/api/v1/logs/monitor-rules/{rule_id}",
        http_method="GET",
        match_mode="exact",
        is_enabled=True,
    )

    ts = datetime(2027, 2, 1, 12, 0, 0, tzinfo=timezone.utc)
    number = log_service.generate_operation_number(ts)

    recorded = log_service.record_operation_log(
        db_session_fixture,
        payload={
            "module": "监听规则",
            "business_type": "query",
            "operator_name": "tester",
            "operator_department": None,
            "operator_ip": "127.0.0.1",
            "operator_location": None,
            "request_method": "GET",
            "request_uri": "/api/v1/logs/monitor-rules/123?foo=1",
            "class_method": "tests.system.test_logs_template.test_template_exact_matches_single_segment",
            "request_params": None,
            "response_params": None,
            "status": "success",
            "error_message": None,
            "cost_ms": 3,
            "operate_time": ts,
        },
        log_number=number,
    )

    assert recorded is not None
    assert recorded.request_uri.startswith("/api/v1/logs/monitor-rules/123")

    # 不应匹配多一级路径
    skipped = log_service.record_operation_log(
        db_session_fixture,
        payload={
            "module": "监听规则",
            "business_type": "query",
            "operator_name": "tester",
            "operator_department": None,
            "operator_ip": "127.0.0.1",
            "operator_location": None,
            "request_method": "GET",
            "request_uri": "/api/v1/logs/monitor-rules/123/extra",
            "class_method": "tests.system.test_logs_template.test_template_exact_matches_single_segment",
            "request_params": None,
            "response_params": None,
            "status": "success",
            "error_message": None,
            "cost_ms": 1,
            "operate_time": ts,
        },
        log_number=log_service.generate_operation_number(ts),
    )
    assert skipped is None


def test_template_prefix_allows_deeper_paths(db_session_fixture: Session):
    # 模板 + 前缀：允许后续更深路径
    _ensure_monitor_rule(
        db_session_fixture,
        request_uri="/api/v1/users/{user_id}",
        http_method="GET",
        match_mode="prefix",
        is_enabled=True,
    )

    ts = datetime(2027, 2, 1, 12, 5, 0, tzinfo=timezone.utc)
    number = log_service.generate_operation_number(ts)

    recorded = log_service.record_operation_log(
        db_session_fixture,
        payload={
            "module": "用户",
            "business_type": "query",
            "operator_name": "tester",
            "operator_department": None,
            "operator_ip": "127.0.0.1",
            "operator_location": None,
            "request_method": "GET",
            "request_uri": "/api/v1/users/42/profile",
            "class_method": "tests.system.test_logs_template.test_template_prefix_allows_deeper_paths",
            "request_params": None,
            "response_params": None,
            "status": "success",
            "error_message": None,
            "cost_ms": 2,
            "operate_time": ts,
        },
        log_number=number,
    )

    assert recorded is not None
    assert recorded.request_uri == "/api/v1/users/42/profile"

    # 再次校验数据库持久化
    stored = (
        db_session_fixture.query(OperationLog)
        .filter(OperationLog.log_number == number)
        .one_or_none()
    )
    assert stored is not None
