"""系统字典相关的路由定义。"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.schemas.dictionary import DictionaryListResponse
from app.core.dependencies import get_current_active_user, get_db
from app.models.user import User
from app.services.dictionary_service import dictionary_service

router = APIRouter(prefix="/dictionaries", tags=["dictionaries"])


@router.get("/{type_code}", response_model=DictionaryListResponse)
def list_dictionary_items(
    type_code: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> DictionaryListResponse:
    """根据类型编码返回字典项列表。"""
    return dictionary_service.list_by_type(db, type_code=type_code)
