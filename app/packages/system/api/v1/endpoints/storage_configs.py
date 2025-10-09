"""存储源配置相关路由。"""

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.packages.system.api.v1.schemas.storage import (
    StorageConfigCreate,
    StorageConfigListResponse,
    StorageConfigMutationResponse,
    StorageConfigUpdate,
    StorageTestResponse,
)
from app.packages.system.core.dependencies import get_current_active_user, get_db
from app.packages.system.models.user import User
from app.packages.system.services.storage_service import storage_service

router = APIRouter(prefix="/storage-configs", tags=["storage-configs"])


@router.get("", response_model=StorageConfigListResponse)
def list_configs(db: Session = Depends(get_db), _: User = Depends(get_current_active_user)):
    return storage_service.list_configs(db)


@router.get("/{config_id}", response_model=StorageConfigMutationResponse)
def get_config(config_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_active_user)):
    return storage_service.get_config(db, id=config_id)


@router.post("", response_model=StorageConfigMutationResponse)
def create_config(payload: StorageConfigCreate, db: Session = Depends(get_db), _: User = Depends(get_current_active_user)):
    return storage_service.create_config(db, payload.model_dump())


@router.put("/{config_id}", response_model=StorageConfigMutationResponse)
def update_config(
    payload: StorageConfigUpdate,
    config_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    return storage_service.update_config(db, id=config_id, payload=payload.model_dump(exclude_unset=True))


@router.delete("/{config_id}", response_model=StorageConfigMutationResponse)
def delete_config(config_id: int = Path(..., ge=1), db: Session = Depends(get_db), _: User = Depends(get_current_active_user)):
    return storage_service.delete_config(db, id=config_id)


@router.post("/test", response_model=StorageTestResponse)
def test_config(payload: StorageConfigCreate, db: Session = Depends(get_db), _: User = Depends(get_current_active_user)):
    return storage_service.test_connection(db, payload.model_dump())
