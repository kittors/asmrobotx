"""CRUD 基类：为各实体提供通用的数据访问方法。"""

from typing import Any, Dict, Generic, List, Optional, Type, TypeVar

from sqlalchemy.orm import Session

from app.packages.system.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class CRUDBase(Generic[ModelType]):
    """封装常见的查询、创建与保存逻辑，减少重复代码。"""

    def __init__(self, model: Type[ModelType]):
        self.model = model

    def get(self, db: Session, id: Any) -> Optional[ModelType]:
        query = db.query(self.model).filter(self.model.id == id)
        if hasattr(self.model, "is_deleted"):
            query = query.filter(self.model.is_deleted.is_(False))
        return query.first()

    def get_multi(self, db: Session, *, skip: int = 0, limit: int = 100) -> List[ModelType]:
        query = db.query(self.model)
        if hasattr(self.model, "is_deleted"):
            query = query.filter(self.model.is_deleted.is_(False))
        return query.offset(skip).limit(limit).all()

    def create(self, db: Session, obj_in: Dict[str, Any]) -> ModelType:
        db_obj = self.model(**obj_in)
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
