"""CRUD 基类：为各实体提供通用的数据访问方法。"""

from typing import Any, Dict, Generic, List, Optional, Type, TypeVar

from sqlalchemy.orm import Session
from app.core.datascope import apply_data_scope, scope_defaults_for_create
from app.packages.system.core.constants import DEFAULT_ORGANIZATION_NAME
from app.packages.system.models.organization import Organization

from app.packages.system.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class CRUDBase(Generic[ModelType]):
    """封装常见的查询、创建与保存逻辑，减少重复代码。"""

    def __init__(self, model: Type[ModelType]):
        self.model = model

    def get(self, db: Session, id: Any) -> Optional[ModelType]:
        query = self.query(db).filter(self.model.id == id)
        return query.first()

    def get_multi(self, db: Session, *, skip: int = 0, limit: int = 100) -> List[ModelType]:
        query = self.query(db)
        return query.offset(skip).limit(limit).all()

    def create(self, db: Session, obj_in: Dict[str, Any]) -> ModelType:
        # 自动附加数据域默认字段（若模型包含且调用方未显式赋值）
        defaults = scope_defaults_for_create(self.model)
        payload = {**defaults, **obj_in}

        # 强制补齐必填字段：若仍缺失，使用“admin(1)/默认组织(研发部)”作为兜底
        if hasattr(self.model, "created_by") and payload.get("created_by") is None:
            payload["created_by"] = 1
        if hasattr(self.model, "organization_id") and payload.get("organization_id") is None:
            org_id = None
            try:
                row = (
                    db.query(Organization.id)
                    .filter(Organization.name == DEFAULT_ORGANIZATION_NAME)
                    .first()
                )
                if row:
                    org_id = row[0] if not isinstance(row, Organization) else row.id
            except Exception:
                org_id = None
            if org_id is None:
                # 如果默认组织不存在，明确报错，避免写入不合法数据
                raise ValueError(
                    "organization_id is required but missing; default organization not found"
                )
            payload["organization_id"] = org_id
        db_obj = self.model(**payload)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def save(self, db: Session, db_obj: ModelType) -> ModelType:
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def soft_delete(self, db: Session, db_obj: ModelType) -> ModelType:
        """执行软删除，如果模型支持软删除字段则仅标记。"""

        if hasattr(db_obj, "is_deleted"):
            setattr(db_obj, "is_deleted", True)
            db.add(db_obj)
        else:
            db.delete(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    # 统一构造带软删除与数据域过滤的查询
    def query(self, db: Session, *, include_deleted: bool = False):
        query = db.query(self.model)
        if hasattr(self.model, "is_deleted") and not include_deleted:
            query = query.filter(self.model.is_deleted.is_(False))
        # 数据隔离：若模型具备 organization_id 字段，则按当前数据域过滤
        query = apply_data_scope(query, self.model)
        return query
