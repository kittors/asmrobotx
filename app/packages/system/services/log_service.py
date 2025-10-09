"""日志管理业务逻辑封装。"""

from __future__ import annotations

import io
import json
from datetime import datetime
from typing import Iterable, Optional

from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.packages.system.core.constants import (
    HTTP_STATUS_BAD_REQUEST,
    HTTP_STATUS_CONFLICT,
    HTTP_STATUS_CREATED,
    HTTP_STATUS_NOT_FOUND,
    HTTP_STATUS_OK,
)
from app.packages.system.core.responses import create_response
from app.packages.system.core.timezone import format_datetime
from app.packages.system.crud.logs import login_log_crud, operation_log_crud
from app.packages.system.crud.operation_log_monitor_rules import operation_log_monitor_rule_crud
from app.packages.system.models.log import LoginLog, OperationLog, OperationLogMonitorRule


class LogService:
    """提供操作日志与登录日志的聚合服务。"""

    _OPERATION_TYPE_LABELS = {
        "create": "新增",
        "update": "修改",
        "delete": "删除",
        "query": "查询",
        "grant": "授权",
        "export": "导出",
        "import": "导入",
        "force_logout": "强退",
        "clean": "清除数据",
        "other": "其他",
    }

    _OPERATION_STATUS_LABELS = {
        "success": "成功",
        "failure": "失败",
    }

    _LOGIN_STATUS_LABELS = {
        "success": "成功",
        "failure": "失败",
    }

    def list_operation_logs(
        self,
        db: Session,
        *,
        module: Optional[str] = None,
        operator_name: Optional[str] = None,
        operator_ip: Optional[str] = None,
        operation_types: Optional[Iterable[str]] = None,
        statuses: Optional[Iterable[str]] = None,
        request_uri: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        normalized_types = self._normalize_operation_types(operation_types)
        normalized_statuses = self._normalize_statuses(statuses)

        page = max(page, 1)
        page_size = max(page_size, 1)

        items, total = operation_log_crud.list_with_filters(
            db,
            module=module,
            operator_name=operator_name,
            operator_ip=operator_ip,
            business_types=normalized_types,
            statuses=normalized_statuses,
            request_uri=request_uri,
            start_time=start_time,
            end_time=end_time,
            skip=(page - 1) * page_size,
            limit=page_size,
        )

        payload = {
            "total": total,
            "items": [self._serialize_operation_log_item(item) for item in items],
            "page": page,
            "page_size": page_size,
        }
        return create_response("获取操作日志成功", payload, HTTP_STATUS_OK)

    def get_operation_log_detail(self, db: Session, *, log_number: str) -> dict:
        log = operation_log_crud.get_by_number(db, log_number=log_number)
        if log is None:
            raise HTTPException(status_code=HTTP_STATUS_NOT_FOUND, detail="操作日志不存在")

        data = self._serialize_operation_log_detail(log)
        return create_response("获取操作日志详情成功", data, HTTP_STATUS_OK)

    def delete_operation_log(self, db: Session, *, log_number: str) -> dict:
        affected = operation_log_crud.remove_by_number(db, log_number=log_number)
        if affected == 0:
            raise HTTPException(status_code=HTTP_STATUS_NOT_FOUND, detail="操作日志不存在或已删除")
        db.commit()
        return create_response("删除操作日志成功", {"log_number": log_number}, HTTP_STATUS_OK)

    def clear_operation_logs(self, db: Session) -> dict:
        operation_log_crud.clear_all(db)
        db.commit()
        return create_response("清除操作日志成功", None, HTTP_STATUS_OK)

    def export_operation_logs(
        self,
        db: Session,
        *,
        module: Optional[str] = None,
        operator_name: Optional[str] = None,
        operator_ip: Optional[str] = None,
        operation_types: Optional[Iterable[str]] = None,
        statuses: Optional[Iterable[str]] = None,
        request_uri: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> StreamingResponse:
        normalized_types = self._normalize_operation_types(operation_types)
        normalized_statuses = self._normalize_statuses(statuses)

        items, _ = operation_log_crud.list_with_filters(
            db,
            module=module,
            operator_name=operator_name,
            operator_ip=operator_ip,
            business_types=normalized_types,
            statuses=normalized_statuses,
            request_uri=request_uri,
            start_time=start_time,
            end_time=end_time,
            skip=0,
            limit=10_000,
        )

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "操作日志"
        headers = [
            "日志编号",
            "系统模块",
            "操作类型",
            "操作人员",
            "操作地址",
            "请求地址",
            "操作状态",
            "操作时间",
            "消耗时间(ms)",
        ]
        sheet.append(headers)

        for item in items:
            sheet.append(
                [
                    item.log_number,
                    item.module,
                    self._display_operation_type(item.business_type),
                    item.operator_name,
                    item.operator_ip or "",
                    item.request_uri or "",
                    self._display_operation_status(item.status),
                    self._format_datetime(item.operate_time),
                    item.cost_ms,
                ]
            )

        buffer = io.BytesIO()
        workbook.save(buffer)
        buffer.seek(0)

        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        filename = f"operation-logs-{timestamp}.xlsx"
        response = StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response.headers["Content-Disposition"] = f"attachment; filename={filename}"
        return response

    def list_login_logs(
        self,
        db: Session,
        *,
        username: Optional[str] = None,
        ip_address: Optional[str] = None,
        statuses: Optional[Iterable[str]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        normalized_statuses = self._normalize_statuses(statuses)
        page = max(page, 1)
        page_size = max(page_size, 1)

        items, total = login_log_crud.list_with_filters(
            db,
            username=username,
            ip_address=ip_address,
            statuses=normalized_statuses,
            start_time=start_time,
            end_time=end_time,
            skip=(page - 1) * page_size,
            limit=page_size,
        )

        payload = {
            "total": total,
            "items": [self._serialize_login_log_item(item) for item in items],
            "page": page,
            "page_size": page_size,
        }
        return create_response("获取登录日志成功", payload, HTTP_STATUS_OK)

    def delete_login_log(self, db: Session, *, visit_number: str) -> dict:
        affected = login_log_crud.remove_by_number(db, visit_number=visit_number)
        if affected == 0:
            raise HTTPException(status_code=HTTP_STATUS_NOT_FOUND, detail="登录日志不存在或已删除")
        db.commit()
        return create_response("删除登录日志成功", {"visit_number": visit_number}, HTTP_STATUS_OK)

    def clear_login_logs(self, db: Session) -> dict:
        login_log_crud.clear_all(db)
        db.commit()
        return create_response("清除登录日志成功", None, HTTP_STATUS_OK)

    def record_operation_log(
        self,
        db: Session,
        *,
        payload: dict,
        log_number: Optional[str] = None,
    ) -> Optional[OperationLog]:
        if not self._should_record_operation_log(db, payload):
            return None

        serial = log_number or self.generate_operation_number()
        obj = operation_log_crud.create(db, payload | {"log_number": serial})
        return obj

    def record_login_log(
        self,
        db: Session,
        *,
        payload: dict,
        visit_number: Optional[str] = None,
    ) -> LoginLog:
        serial = visit_number or self.generate_visit_number()
        obj = login_log_crud.create(db, payload | {"visit_number": serial})
        return obj

    # ------------------------------------------------------------------
    # 监听规则维护
    # ------------------------------------------------------------------

    def list_monitor_rules(
        self,
        db: Session,
        *,
        request_uri: Optional[str] = None,
        http_method: Optional[str] = None,
        match_mode: Optional[str] = None,
        is_enabled: Optional[bool] = None,
        operation_type_code: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        page = max(page, 1)
        page_size = max(page_size, 1)

        items, total = operation_log_monitor_rule_crud.list_with_filters(
            db,
            request_uri=request_uri,
            http_method=http_method,
            match_mode=match_mode,
            is_enabled=is_enabled,
            operation_type_code=operation_type_code,
            skip=(page - 1) * page_size,
            limit=page_size,
        )

        payload = {
            "total": total,
            "items": [self._serialize_monitor_rule(item) for item in items],
            "page": page,
            "page_size": page_size,
        }
        return create_response("获取监听规则列表成功", payload, HTTP_STATUS_OK)

    def get_monitor_rule(self, db: Session, *, rule_id: int) -> dict:
        rule = operation_log_monitor_rule_crud.get(db, rule_id)
        if rule is None:
            raise HTTPException(status_code=HTTP_STATUS_NOT_FOUND, detail="监听规则不存在")
        return create_response("获取监听规则详情成功", self._serialize_monitor_rule(rule), HTTP_STATUS_OK)

    def create_monitor_rule(self, db: Session, *, payload: dict) -> dict:
        normalized = self._normalize_monitor_rule_payload(payload)

        self._ensure_monitor_rule_unique(
            db,
            request_uri=normalized.get("request_uri"),
            http_method=normalized.get("http_method", "ALL"),
            match_mode=normalized.get("match_mode", "exact"),
        )

        rule = operation_log_monitor_rule_crud.create(db, normalized)
        return create_response("创建监听规则成功", self._serialize_monitor_rule(rule), HTTP_STATUS_CREATED)

    def update_monitor_rule(self, db: Session, *, rule_id: int, payload: dict) -> dict:
        rule = operation_log_monitor_rule_crud.get(db, rule_id)
        if rule is None:
            raise HTTPException(status_code=HTTP_STATUS_NOT_FOUND, detail="监听规则不存在")

        normalized = self._normalize_monitor_rule_payload(payload, allow_partial=True)

        target_request_uri = normalized.get("request_uri", rule.request_uri)
        target_http_method = normalized.get("http_method", rule.http_method)
        target_match_mode = normalized.get("match_mode", rule.match_mode)

        self._ensure_monitor_rule_unique(
            db,
            request_uri=target_request_uri,
            http_method=target_http_method,
            match_mode=target_match_mode,
            exclude_id=rule.id,
        )

        for key, value in normalized.items():
            setattr(rule, key, value)

        updated = operation_log_monitor_rule_crud.save(db, rule)
        return create_response("更新监听规则成功", self._serialize_monitor_rule(updated), HTTP_STATUS_OK)

    def delete_monitor_rule(self, db: Session, *, rule_id: int) -> dict:
        rule = operation_log_monitor_rule_crud.get(db, rule_id)
        if rule is None:
            raise HTTPException(status_code=HTTP_STATUS_NOT_FOUND, detail="监听规则不存在")

        operation_log_monitor_rule_crud.soft_delete(db, rule)
        return create_response("删除监听规则成功", {"rule_id": rule_id}, HTTP_STATUS_OK)

    def _should_record_operation_log(self, db: Session, payload: dict) -> bool:
        """根据数据库配置判断本次请求是否需要采集操作日志。"""

        request_uri = payload.get("request_uri")
        if not request_uri:
            # 缺少请求路径时无法匹配监听规则，默认不记录。
            return False

        request_method = payload.get("request_method")
        rule = operation_log_monitor_rule_crud.find_matching_rule(
            db,
            request_uri=str(request_uri),
            http_method=str(request_method) if request_method else None,
        )
        if rule is None:
            # 未配置规则则不记录，需显式开启。
            return False
        return bool(rule.is_enabled)

    def _serialize_monitor_rule(self, rule: OperationLogMonitorRule) -> dict:
        return {
            "id": rule.id,
            "name": rule.name,
            "request_uri": rule.request_uri,
            "http_method": rule.http_method,
            "match_mode": rule.match_mode,
            "is_enabled": rule.is_enabled,
            "description": rule.description,
            "operation_type_code": rule.operation_type_code,
            "operation_type_label": self._display_operation_type(rule.operation_type_code),
            "create_time": self._format_datetime(rule.create_time),
            "update_time": self._format_datetime(rule.update_time),
        }

    def _normalize_monitor_rule_payload(self, payload: dict, *, allow_partial: bool = False) -> dict:
        if payload is None:
            payload = {}

        normalized: dict[str, Optional[str]] = {}

        def _strip(value: Optional[str]) -> Optional[str]:
            if value is None:
                return None
            text = str(value).strip()
            return text or None

        if not allow_partial or "request_uri" in payload:
            request_uri = _strip(payload.get("request_uri"))
            if not request_uri:
                if allow_partial:
                    pass
                else:
                    raise HTTPException(status_code=HTTP_STATUS_BAD_REQUEST, detail="请求地址不能为空")
            else:
                normalized["request_uri"] = request_uri

        if not allow_partial or "http_method" in payload:
            http_method = payload.get("http_method")
            if http_method is None:
                method_value = "ALL"
            else:
                method_value = str(http_method).strip().upper()
            if not method_value:
                raise HTTPException(status_code=HTTP_STATUS_BAD_REQUEST, detail="HTTP 方法不能为空")
            normalized["http_method"] = method_value

        if not allow_partial or "match_mode" in payload:
            match_mode = payload.get("match_mode")
            mode_value = str(match_mode).strip().lower() if match_mode is not None else "exact"
            if mode_value not in {"exact", "prefix"}:
                raise HTTPException(status_code=HTTP_STATUS_BAD_REQUEST, detail="匹配模式仅支持 exact 或 prefix")
            normalized["match_mode"] = mode_value

        if not allow_partial or "is_enabled" in payload:
            if "is_enabled" in payload:
                normalized["is_enabled"] = bool(payload.get("is_enabled"))
            elif not allow_partial:
                normalized["is_enabled"] = True

        if not allow_partial or "name" in payload:
            normalized["name"] = _strip(payload.get("name"))

        if not allow_partial or "description" in payload:
            normalized["description"] = _strip(payload.get("description"))

        if not allow_partial or "operation_type_code" in payload:
            code = payload.get("operation_type_code")
            if code is None:
                normalized["operation_type_code"] = None
            else:
                normalized["operation_type_code"] = _strip(code.lower()) if isinstance(code, str) else _strip(code)

        return normalized

    def _ensure_monitor_rule_unique(
        self,
        db: Session,
        *,
        request_uri: Optional[str],
        http_method: Optional[str],
        match_mode: Optional[str],
        exclude_id: Optional[int] = None,
    ) -> None:
        if not request_uri or not http_method or not match_mode:
            return

        existing = operation_log_monitor_rule_crud.get_by_unique(
            db,
            request_uri=request_uri,
            http_method=http_method,
            match_mode=match_mode,
            exclude_id=exclude_id,
        )

        if existing is not None:
            raise HTTPException(status_code=HTTP_STATUS_CONFLICT, detail="监听规则已存在")

    # ------------------------------------------------------------------
    # 底层辅助方法
    # ------------------------------------------------------------------

    @classmethod
    def _normalize_operation_types(cls, types: Optional[Iterable[str]]) -> Optional[list[str]]:
        if not types:
            return None
        normalized: list[str] = []
        for item in types:
            if not item:
                continue
            token = item.strip()
            code = cls._reverse_operation_label(token)
            normalized.append(code)
        return normalized or None

    @classmethod
    def _normalize_statuses(cls, statuses: Optional[Iterable[str]]) -> Optional[list[str]]:
        if not statuses:
            return None
        normalized: list[str] = []
        for status in statuses:
            if not status:
                continue
            token = status.strip().lower()
            if token in cls._OPERATION_STATUS_LABELS:
                normalized.append(token)
            elif token in cls._OPERATION_STATUS_LABELS.values():
                normalized.append(cls._reverse_status_label(token))
            else:
                raise HTTPException(status_code=HTTP_STATUS_BAD_REQUEST, detail="未知的状态过滤值")
        return normalized or None

    @classmethod
    def _reverse_operation_label(cls, label: str) -> str:
        lower_label = label.strip().lower()
        for code, zh in cls._OPERATION_TYPE_LABELS.items():
            if lower_label == code:
                return code
            if label.strip() == zh:
                return code
        raise HTTPException(status_code=HTTP_STATUS_BAD_REQUEST, detail="未知的操作类型")

    @classmethod
    def _reverse_status_label(cls, label: str) -> str:
        for code, zh in cls._OPERATION_STATUS_LABELS.items():
            if label.strip() == zh:
                return code
        raise HTTPException(status_code=HTTP_STATUS_BAD_REQUEST, detail="未知的状态过滤值")

    def _serialize_operation_log_item(self, item: OperationLog) -> dict:
        return {
            "log_number": item.log_number,
            "module": item.module,
            "operation_type": self._display_operation_type(item.business_type),
            "operation_type_code": item.business_type,
            "operator_name": item.operator_name,
            "operator_ip": item.operator_ip,
            "request_uri": item.request_uri,
            "status": self._display_operation_status(item.status),
            "status_code": item.status,
            "operate_time": self._format_datetime(item.operate_time),
            "cost_ms": item.cost_ms,
        }

    def _serialize_operation_log_detail(self, item: OperationLog) -> dict:
        return {
            "log_number": item.log_number,
            "login_info": {
                "username": item.operator_name,
                "department": item.operator_department,
                "ip_address": item.operator_ip,
                "location": item.operator_location,
            },
            "request_info": {
                "method": item.request_method,
                "uri": item.request_uri,
            },
            "operation_module": {
                "module": item.module,
                "operation_type": self._display_operation_type(item.business_type),
                "operation_type_code": item.business_type,
            },
            "class_method": item.class_method,
            "request_params": self._format_json_block(item.request_params),
            "response_params": self._format_json_block(item.response_params),
            "status": self._display_operation_status(item.status),
            "status_code": item.status,
            "cost_ms": item.cost_ms,
            "operate_time": self._format_datetime(item.operate_time),
            "error_message": item.error_message,
        }

    def _serialize_login_log_item(self, item: LoginLog) -> dict:
        return {
            "visit_number": item.visit_number,
            "username": item.username,
            "client_name": item.client_name,
            "device_type": item.device_type,
            "ip_address": item.ip_address,
            "login_location": item.login_location,
            "operating_system": item.operating_system,
            "browser": item.browser,
            "status": self._display_login_status(item.status),
            "status_code": item.status,
            "message": item.message,
            "login_time": self._format_datetime(item.login_time),
        }

    def _display_operation_type(self, code: Optional[str]) -> str:
        if not code:
            return "其他"
        return self._OPERATION_TYPE_LABELS.get(code, code)

    def _display_operation_status(self, code: Optional[str]) -> str:
        if not code:
            return "未知"
        return self._OPERATION_STATUS_LABELS.get(code, code)

    def _display_login_status(self, code: Optional[str]) -> str:
        if not code:
            return "未知"
        return self._LOGIN_STATUS_LABELS.get(code, code)

    @staticmethod
    def _format_datetime(value: Optional[datetime]) -> Optional[str]:
        return format_datetime(value)

    @staticmethod
    def _format_json_block(value: Optional[str]) -> str:
        if not value:
            return "{}"
        stripped = value.strip()
        if not stripped:
            return "{}"
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return stripped
        return json.dumps(parsed, ensure_ascii=False, indent=2)

    @staticmethod
    def generate_operation_number(timestamp: Optional[datetime] = None) -> str:
        moment = timestamp or datetime.utcnow()
        return moment.strftime("%Y%m%d%H%M%S%f")

    @staticmethod
    def generate_visit_number(timestamp: Optional[datetime] = None) -> str:
        moment = timestamp or datetime.utcnow()
        return moment.strftime("%Y%m%d%H%M%S%f")


log_service = LogService()
