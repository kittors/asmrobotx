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

from app.core.constants import (
    HTTP_STATUS_BAD_REQUEST,
    HTTP_STATUS_NOT_FOUND,
    HTTP_STATUS_OK,
)
from app.core.responses import create_response
from app.crud.logs import login_log_crud, operation_log_crud
from app.models.log import LoginLog, OperationLog


class LogService:
    """提供操作日志与登录日志的聚合服务。"""

    _OPERATION_TYPE_LABELS = {
        "create": "新增",
        "update": "修改",
        "delete": "删除",
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
    ) -> OperationLog:
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
        if value is None:
            return None
        return value.strftime("%Y-%m-%d %H:%M:%S")

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
