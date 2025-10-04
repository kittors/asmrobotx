"""API v1 汇总路由：统一挂载所有版本化的子路由。"""

from fastapi import APIRouter

from app.api.v1.endpoints import access_controls, auth, dictionaries, logs, organizations, roles, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(organizations.router)
api_router.include_router(access_controls.router)
api_router.include_router(roles.router)
api_router.include_router(dictionaries.router)
api_router.include_router(logs.router)
