"""日志相关的 CRUD 操作封装。"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.packages.system.crud.base import CRUDBase
from app.packages.system.models.log import LoginLog, OperationLog


class OperationLogCRUD(CRUDBase[OperationLog]):
    """提供操作日志的查询与维护能力。"""

    def list_with_filters(
        self,
        db: Session,
        *,
        module: Optional[str] = None,
        operator_name: Optional[str] = None,
        operator_ip: Optional[str] = None,
        business_types: Optional[Iterable[str]] = None,
        statuses: Optional[Iterable[str]] = None,
        request_uri: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[list[OperationLog], int]:
        query = db.query(self.model).filter(self.model.is_deleted.is_(False))

        if module:
            query = query.filter(self.model.module.ilike(f"%{module.strip()}%"))
        if operator_name:
            query = query.filter(self.model.operator_name.ilike(f"%{operator_name.strip()}%"))
        if operator_ip:
            query = query.filter(self.model.operator_ip.ilike(f"%{operator_ip.strip()}%"))
        if request_uri:
            query = query.filter(self.model.request_uri.ilike(f"%{request_uri.strip()}%"))
        if business_types:
            query = query.filter(self.model.business_type.in_(set(business_types)))
        if statuses:
            query = query.filter(self.model.status.in_(set(statuses)))
        if start_time and end_time:
            query = query.filter(
                self.model.operate_time.between(start_time, end_time),
            )
        elif start_time:
            query = query.filter(self.model.operate_time >= start_time)
        elif end_time:
            query = query.filter(self.model.operate_time <= end_time)

        total = query.count()
        items = (
            query.order_by(self.model.operate_time.desc(), self.model.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, total

    def get_by_number(self, db: Session, *, log_number: str) -> Optional[OperationLog]:
        return (
            db.query(self.model)
            .filter(
                self.model.log_number == log_number,
                self.model.is_deleted.is_(False),
            )
            .first()
        )

    def remove_by_number(self, db: Session, *, log_number: str) -> int:
        return (
            db.query(self.model)
            .filter(
                self.model.log_number == log_number,
                self.model.is_deleted.is_(False),
            )
            .update({self.model.is_deleted: True, self.model.update_time: func.now()})
        )

    def clear_all(self, db: Session) -> int:
        return (
            db.query(self.model)
            .filter(self.model.is_deleted.is_(False))
            .update({self.model.is_deleted: True, self.model.update_time: func.now()})
        )


class LoginLogCRUD(CRUDBase[LoginLog]):
    """提供登录日志的查询接口。"""

    def list_with_filters(
        self,
        db: Session,
        *,
        username: Optional[str] = None,
        ip_address: Optional[str] = None,
        statuses: Optional[Iterable[str]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[list[LoginLog], int]:
        query = db.query(self.model).filter(self.model.is_deleted.is_(False))

        if username:
            query = query.filter(self.model.username.ilike(f"%{username.strip()}%"))
        if ip_address:
            query = query.filter(self.model.ip_address.ilike(f"%{ip_address.strip()}%"))
        if statuses:
            query = query.filter(self.model.status.in_(set(statuses)))
        if start_time and end_time:
            query = query.filter(self.model.login_time.between(start_time, end_time))
        elif start_time:
            query = query.filter(self.model.login_time >= start_time)
        elif end_time:
            query = query.filter(self.model.login_time <= end_time)

        total = query.count()
        items = (
            query.order_by(self.model.login_time.desc(), self.model.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, total

    def get_by_number(self, db: Session, *, visit_number: str) -> Optional[LoginLog]:
        return (
            db.query(self.model)
            .filter(
                self.model.visit_number == visit_number,
                self.model.is_deleted.is_(False),
            )
            .first()
        )

    def remove_by_number(self, db: Session, *, visit_number: str) -> int:
        return (
            db.query(self.model)
            .filter(
                self.model.visit_number == visit_number,
                self.model.is_deleted.is_(False),
            )
            .update({self.model.is_deleted: True, self.model.update_time: func.now()})
        )

    def clear_all(self, db: Session) -> int:
        return (
            db.query(self.model)
            .filter(self.model.is_deleted.is_(False))
            .update({self.model.is_deleted: True, self.model.update_time: func.now()})
        )


operation_log_crud = OperationLogCRUD(OperationLog)
login_log_crud = LoginLogCRUD(LoginLog)
