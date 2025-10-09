"""操作日志监控规则的数据库访问封装。"""

from __future__ import annotations

from typing import Optional, Tuple

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.packages.system.crud.base import CRUDBase
from app.packages.system.models.log import OperationLogMonitorRule


class OperationLogMonitorRuleCRUD(CRUDBase[OperationLogMonitorRule]):
    """提供根据 URI/方法匹配监控规则的便捷接口。"""

    def find_matching_rule(
        self,
        db: Session,
        *,
        request_uri: str,
        http_method: Optional[str],
    ) -> Optional[OperationLogMonitorRule]:
        """返回与请求最匹配的监控规则，支持前缀与精确匹配优先级。"""

        if not request_uri:
            return None

        normalized_method = (http_method or "ALL").upper()
        candidates = (
            db.query(self.model)
            .filter(
                self.model.is_deleted.is_(False),
                or_(
                    self.model.http_method == normalized_method,
                    self.model.http_method == "ALL",
                ),
            )
            .all()
        )

        best_match: Optional[Tuple[Tuple[int, int, int, int], OperationLogMonitorRule]] = None
        for rule in candidates:
            if rule.match_mode == "exact":
                matched = request_uri == rule.request_uri
                mode_score = 2
            else:
                matched = request_uri.startswith(rule.request_uri)
                mode_score = 1

            if not matched:
                continue

            method_score = 2 if rule.http_method == normalized_method else 1
            length_score = len(rule.request_uri)

            current_rank = (mode_score, method_score, length_score, rule.id)
            if best_match is None or current_rank > best_match[0]:
                best_match = (current_rank, rule)

        return best_match[1] if best_match else None

    def list_disabled_rules(self, db: Session) -> list[OperationLogMonitorRule]:
        """列出所有显式禁用的监听规则。"""

        return (
            db.query(self.model)
            .filter(
                self.model.is_deleted.is_(False),
                self.model.is_enabled.is_(False),
            )
            .all()
        )

    def list_with_filters(
        self,
        db: Session,
        *,
        request_uri: Optional[str] = None,
        http_method: Optional[str] = None,
        match_mode: Optional[str] = None,
        is_enabled: Optional[bool] = None,
        operation_type_code: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
        ) -> Tuple[list[OperationLogMonitorRule], int]:
        """按条件分页查询监听规则列表。"""

        query = db.query(self.model).filter(self.model.is_deleted.is_(False))

        if request_uri:
            query = query.filter(self.model.request_uri.ilike(f"%{request_uri.strip()}%"))
        if http_method:
            query = query.filter(self.model.http_method == http_method.strip().upper())
        if match_mode:
            query = query.filter(self.model.match_mode == match_mode.strip().lower())
        if is_enabled is not None:
            query = query.filter(self.model.is_enabled.is_(bool(is_enabled)))
        if operation_type_code:
            normalized_code = operation_type_code.strip().lower()
            query = query.filter(
                func.lower(func.coalesce(self.model.operation_type_code, "")) == normalized_code
            )

        total = query.count()
        items = (
            query.order_by(self.model.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, total

    def get_by_unique(
        self,
        db: Session,
        *,
        request_uri: str,
        http_method: str,
        match_mode: str,
        exclude_id: Optional[int] = None,
    ) -> Optional[OperationLogMonitorRule]:
        """根据唯一键检索监听规则，排除软删除记录。"""

        query = (
            db.query(self.model)
            .filter(
                self.model.is_deleted.is_(False),
                self.model.request_uri == request_uri,
                self.model.http_method == http_method,
                self.model.match_mode == match_mode,
            )
        )

        if exclude_id is not None:
            query = query.filter(self.model.id != exclude_id)

        return query.first()


operation_log_monitor_rule_crud = OperationLogMonitorRuleCRUD(OperationLogMonitorRule)
