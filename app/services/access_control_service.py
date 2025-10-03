"""访问控制相关的业务逻辑封装。"""

from __future__ import annotations

from collections import defaultdict
import re
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from app.core.constants import (
    HTTP_STATUS_BAD_REQUEST,
    HTTP_STATUS_CONFLICT,
    HTTP_STATUS_NOT_FOUND,
    HTTP_STATUS_OK,
)
from app.core.enums import AccessControlTypeEnum
from app.core.exceptions import AppException
from app.core.responses import create_response
from app.crud.access_control import access_control_crud
from app.models.access_control import AccessControlItem


class AccessControlService:
    """聚合访问控制项的增删改查逻辑。"""

    _STATUS_VALUE_MAP = {
        "启用": "enabled",
        "停用": "disabled",
    }
    _DISPLAY_STATUS_VALUE_MAP = {
        "显示": "show",
        "隐藏": "hidden",
    }
    _TYPE_FALLBACK_MAP = {
        "directory": AccessControlTypeEnum.MENU.value,
    }

    def list_tree(
        self,
        db: Session,
        *,
        name: Optional[str] = None,
        enabled_status: Optional[str] = None,
    ) -> dict[str, Any]:
        """按照树形结构返回访问控制项集合。"""

        items = access_control_crud.list_all(db)
        if not items:
            return create_response("获取访问控制列表成功", [], HTTP_STATUS_OK)

        normalized_status = self._normalize_status(enabled_status)
        name_filter = name.strip().lower() if name else None

        children_map: Dict[Optional[int], List[AccessControlItem]] = defaultdict(list)
        for item in items:
            children_map[item.parent_id].append(item)

        for siblings in children_map.values():
            siblings.sort(key=lambda node: (node.sort_order, node.id))

        if name_filter or normalized_status:
            include_map: Dict[int, bool] = {}
            match_map: Dict[int, bool] = {}

            for item in items:
                name_match = True
                status_match = True
                if name_filter:
                    name_match = name_filter in item.name.lower()
                if normalized_status:
                    status_match = item.enabled_status == normalized_status
                match_map[item.id] = name_match and status_match

            def should_include(node: AccessControlItem) -> bool:
                if node.id in include_map:
                    return include_map[node.id]
                include_self = match_map.get(node.id, False)
                include_children = any(should_include(child) for child in children_map.get(node.id, []))
                include_map[node.id] = include_self or include_children
                return include_map[node.id]

            filtered_roots = [
                node
                for node in children_map.get(None, [])
                if should_include(node)
            ]
        else:
            include_map = {item.id: True for item in items}
            filtered_roots = children_map.get(None, [])

        def build_node(
            node: AccessControlItem,
            parent_display: Optional[str],
            parent_enabled: Optional[str],
        ) -> Dict[str, Any]:
            if not include_map.get(node.id, False):
                raise AppException("节点过滤状态异常", HTTP_STATUS_BAD_REQUEST)

            display_status = node.display_status
            effective_display = display_status or parent_display
            if parent_display == "hidden":
                effective_display = "hidden"

            enabled_status_value = node.enabled_status
            effective_enabled = enabled_status_value
            if parent_enabled == "disabled":
                effective_enabled = "disabled"

            children_payload = [
                build_node(child, effective_display, effective_enabled)
                for child in children_map.get(node.id, [])
                if include_map.get(child.id, False)
            ]

            normalized_type = self._normalize_type_value(node.type)

            return {
                "id": node.id,
                "parent_id": node.parent_id,
                "name": node.name,
                "type": normalized_type,
                "icon": node.icon,
                "is_external": bool(node.is_external),
                "permission_code": node.permission_code,
                "route_path": node.route_path,
                "display_status": display_status,
                "enabled_status": enabled_status_value,
                "effective_display_status": effective_display,
                "effective_enabled_status": effective_enabled,
                "sort_order": node.sort_order,
                "component_path": node.component_path,
                "route_params": node.route_params or {},
                "keep_alive": bool(node.keep_alive),
                "children": children_payload,
            }

        tree = [
            build_node(root, None, None)
            for root in filtered_roots
            if include_map.get(root.id, False)
        ]
        return create_response("获取访问控制列表成功", tree, HTTP_STATUS_OK)

    def get_routers(self, db: Session) -> dict[str, Any]:
        """构建前端动态路由所需的菜单结构。"""

        items = access_control_crud.list_all(db)
        menus = [
            item
            for item in items
            if self._normalize_type_value(item.type) == AccessControlTypeEnum.MENU.value
            and (item.enabled_status or "enabled").strip().lower() == "enabled"
        ]

        if not menus:
            return create_response("获取路由成功", [], HTTP_STATUS_OK)

        children_map: Dict[Optional[int], List[AccessControlItem]] = defaultdict(list)
        for menu in menus:
            parent_key = menu.parent_id or None
            children_map[parent_key].append(menu)

        for siblings in children_map.values():
            siblings.sort(key=lambda node: (node.sort_order, node.id))

        roots = children_map.get(None, [])
        payload = [self._serialize_router_node(root, children_map, None) for root in roots]
        return create_response("获取路由成功", payload, HTTP_STATUS_OK)

    def get_detail(self, db: Session, *, item_id: int) -> dict[str, Any]:
        """返回指定访问控制项的详情。"""

        item = access_control_crud.get(db, item_id)
        if item is None:
            raise AppException("访问控制项不存在", HTTP_STATUS_NOT_FOUND)

        data = self._serialize_item(item)
        return create_response("获取访问控制项详情成功", data, HTTP_STATUS_OK)

    def create(self, db: Session, *, payload: Dict[str, Any]) -> dict[str, Any]:
        """创建新的访问控制项。"""

        parent = None
        parent_id = payload.get("parent_id")
        if parent_id in (0, "0"):
            parent_id = None

        node_type = self._normalize_type_value(payload.get("type"))
        payload["type"] = node_type

        if parent_id is not None:
            parent = access_control_crud.get(db, parent_id)
            if parent is None:
                raise AppException("上级访问控制项不存在", HTTP_STATUS_NOT_FOUND)
            parent_type = self._normalize_type_value(parent.type)
            if parent.type != parent_type:
                parent.type = parent_type
            if parent_type == AccessControlTypeEnum.BUTTON.value:
                raise AppException("按钮类型不允许继续添加子项", HTTP_STATUS_BAD_REQUEST)
        else:
            parent = None

        if parent is None and node_type != AccessControlTypeEnum.MENU.value:
            raise AppException("根节点必须是菜单类型", HTTP_STATUS_BAD_REQUEST)

        name_value = self._normalize_name(payload.get("name"))
        if not name_value:
            raise AppException("名称必填", HTTP_STATUS_BAD_REQUEST)

        permission_code = self._normalize_permission_code(payload.get("permission_code"))

        if node_type == AccessControlTypeEnum.BUTTON.value and not permission_code:
            raise AppException("按钮必须提供权限字符", HTTP_STATUS_BAD_REQUEST)

        if permission_code:
            self._ensure_unique_permission_code(db, permission_code)
        self._normalize_payload_by_type(node_type, payload)

        if node_type == AccessControlTypeEnum.BUTTON.value:
            payload["is_external"] = False

        enabled_status_value = payload.get("enabled_status")
        display_status_value = payload.get("display_status")
        route_path_value = payload.get("route_path")
        component_path_value = payload.get("component_path")
        route_params_value = payload.get("route_params")
        keep_alive_value = bool(payload.get("keep_alive", False))

        db_obj = access_control_crud.create(
            db,
            {
                "parent_id": parent_id,
                "name": name_value,
                "type": node_type,
                "icon": payload.get("icon"),
                "is_external": bool(payload.get("is_external", False)),
                "permission_code": permission_code,
                "route_path": route_path_value,
                "display_status": display_status_value,
                "enabled_status": enabled_status_value,
                "sort_order": payload.get("sort_order", 0),
                "component_path": component_path_value,
                "route_params": route_params_value,
                "keep_alive": keep_alive_value,
            },
        )

        data = self._serialize_item(db_obj)
        return create_response("创建访问控制项成功", data, HTTP_STATUS_OK)

    def update(self, db: Session, *, item_id: int, payload: Dict[str, Any]) -> dict[str, Any]:
        """更新现有访问控制项。"""

        db_obj = access_control_crud.get(db, item_id)
        if db_obj is None:
            raise AppException("访问控制项不存在", HTTP_STATUS_NOT_FOUND)

        name_value = self._normalize_name(payload.get("name"))
        if not name_value:
            raise AppException("名称必填", HTTP_STATUS_BAD_REQUEST)


        node_type = self._normalize_type_value(db_obj.type)
        if db_obj.type != node_type:
            db_obj.type = node_type

        permission_code_supplied = "permission_code" in payload
        if permission_code_supplied:
            permission_code = self._normalize_permission_code(payload.get("permission_code"))
            if node_type == AccessControlTypeEnum.BUTTON.value and not permission_code:
                raise AppException("按钮必须提供权限字符", HTTP_STATUS_BAD_REQUEST)
            if permission_code:
                self._ensure_unique_permission_code(db, permission_code, exclude_id=db_obj.id)
        else:
            permission_code = self._normalize_permission_code(db_obj.permission_code)
            if node_type == AccessControlTypeEnum.BUTTON.value and not permission_code:
                raise AppException("按钮必须提供权限字符", HTTP_STATUS_BAD_REQUEST)

        self._normalize_payload_by_type(node_type, payload)

        if node_type == AccessControlTypeEnum.BUTTON.value:
            payload["is_external"] = False

        route_path_value = payload.get("route_path")
        component_path_value = payload.get("component_path")
        route_params_value = payload.get("route_params")
        keep_alive_value = bool(payload.get("keep_alive", db_obj.keep_alive))

        db_obj.name = name_value
        if "icon" in payload:
            db_obj.icon = payload["icon"]
        if "is_external" in payload:
            db_obj.is_external = bool(payload["is_external"])
        if permission_code_supplied:
            db_obj.permission_code = permission_code
        if "route_path" in payload:
            db_obj.route_path = route_path_value
        if "display_status" in payload:
            db_obj.display_status = payload["display_status"]
        if "enabled_status" in payload:
            db_obj.enabled_status = payload["enabled_status"]
        if "sort_order" in payload:
            db_obj.sort_order = payload["sort_order"]
        if "component_path" in payload:
            db_obj.component_path = component_path_value
        if "route_params" in payload:
            db_obj.route_params = route_params_value
        db_obj.keep_alive = keep_alive_value

        access_control_crud.save(db, db_obj)
        data = self._serialize_item(db_obj)
        return create_response("更新访问控制项成功", data, HTTP_STATUS_OK)

    def delete(self, db: Session, *, item_id: int) -> dict[str, Any]:
        """删除指定访问控制项，删除前需校验子级数量。"""

        db_obj = access_control_crud.get(db, item_id)
        if db_obj is None:
            raise AppException("访问控制项不存在", HTTP_STATUS_NOT_FOUND)

        if access_control_crud.has_children(db, item_id):
            raise AppException("该项包含子项，无法删除", HTTP_STATUS_BAD_REQUEST)

        access_control_crud.soft_delete(db, db_obj)
        return create_response("删除访问控制项成功", None, HTTP_STATUS_OK)

    def _ensure_unique_permission_code(
        self,
        db: Session,
        permission_code: Optional[str],
        *,
        exclude_id: Optional[int] = None,
    ) -> None:
        if permission_code is None:
            return
        existing = access_control_crud.get_by_permission_code(
            db,
            permission_code,
            exclude_id=exclude_id,
        )
        if existing is not None:
            raise AppException("权限字符已存在", HTTP_STATUS_CONFLICT)

    def _normalize_payload_by_type(self, node_type: str, payload: Dict[str, Any]) -> None:
        if node_type == AccessControlTypeEnum.MENU.value:
            payload["display_status"] = self._normalize_display_status(payload.get("display_status"))
            payload["enabled_status"] = self._normalize_enabled_status_value(payload.get("enabled_status"))
            payload["route_path"] = self._normalize_route_path(payload.get("route_path"))
            payload["component_path"] = self._normalize_optional_component_path(payload.get("component_path"))
            payload["route_params"] = self._normalize_route_params(payload.get("route_params"))
            payload["keep_alive"] = bool(payload.get("keep_alive", False))
        else:
            payload["enabled_status"] = self._normalize_enabled_status_value(payload.get("enabled_status"))
            if "display_status" in payload and payload["display_status"] is not None:
                payload["display_status"] = self._normalize_display_status(payload["display_status"])
            if "route_path" in payload:
                payload["route_path"] = self._normalize_route_path(payload["route_path"])
            payload["component_path"] = None
            payload["route_params"] = {}
            payload["keep_alive"] = False

    def _normalize_optional_component_path(self, component_path: Optional[str]) -> Optional[str]:
        if component_path is None:
            return None
        normalized = component_path.strip()
        return normalized or None

    def _normalize_route_params(self, route_params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if route_params is None:
            return {}
        if not isinstance(route_params, dict):
            raise AppException("路由参数必须为对象", HTTP_STATUS_BAD_REQUEST)
        return route_params

    def _normalize_type_value(self, node_type: Optional[Any]) -> str:
        if isinstance(node_type, AccessControlTypeEnum):
            value = node_type.value
        elif node_type is None:
            value = AccessControlTypeEnum.MENU.value
        else:
            value = str(node_type)

        normalized = value.strip().lower()
        normalized = self._TYPE_FALLBACK_MAP.get(normalized, normalized)
        if normalized not in {
            AccessControlTypeEnum.MENU.value,
            AccessControlTypeEnum.BUTTON.value,
        }:
            raise AppException("访问控制项类型无效", HTTP_STATUS_BAD_REQUEST)
        return normalized

    def _normalize_status(self, enabled_status: Optional[str]) -> Optional[str]:
        if enabled_status is None:
            return None
        normalized = enabled_status.strip()
        if not normalized:
            return None
        mapped = self._STATUS_VALUE_MAP.get(normalized)
        value = (mapped or normalized).lower()
        if value == "all":
            return None
        if value not in {"enabled", "disabled"}:
            return None
        return value

    def _normalize_enabled_status_value(self, enabled_status: Optional[str]) -> str:
        if enabled_status is None:
            raise AppException("停用状态必填", HTTP_STATUS_BAD_REQUEST)
        normalized = enabled_status.strip()
        if not normalized:
            raise AppException("停用状态必填", HTTP_STATUS_BAD_REQUEST)
        mapped = self._STATUS_VALUE_MAP.get(normalized, normalized).lower()
        if mapped not in {"enabled", "disabled"}:
            raise AppException("停用状态取值无效", HTTP_STATUS_BAD_REQUEST)
        return mapped

    def _normalize_display_status(self, display_status: Optional[str]) -> str:
        if display_status is None:
            raise AppException("显示状态必填", HTTP_STATUS_BAD_REQUEST)
        normalized = display_status.strip()
        if not normalized:
            raise AppException("显示状态必填", HTTP_STATUS_BAD_REQUEST)
        mapped = self._DISPLAY_STATUS_VALUE_MAP.get(normalized, normalized).lower()
        if mapped not in {"show", "hidden"}:
            raise AppException("显示状态取值无效", HTTP_STATUS_BAD_REQUEST)
        return mapped

    def _normalize_name(self, name: Optional[str]) -> Optional[str]:
        if name is None:
            return None
        return name.strip()

    def _normalize_route_path(self, route_path: Optional[str]) -> Optional[str]:
        if route_path is None:
            return None
        normalized = route_path.strip()
        return normalized or None

    def _normalize_permission_code(self, permission_code: Optional[Any]) -> Optional[str]:
        if permission_code is None:
            return None
        normalized = str(permission_code).strip()
        return normalized or None

    def _serialize_item(self, item: AccessControlItem) -> Dict[str, Any]:
        return {
            "id": item.id,
            "parent_id": item.parent_id,
            "name": item.name,
            "type": self._normalize_type_value(item.type),
            "icon": item.icon,
            "is_external": bool(item.is_external),
            "permission_code": item.permission_code,
            "route_path": item.route_path,
            "display_status": item.display_status,
            "enabled_status": item.enabled_status,
            "sort_order": item.sort_order,
            "component_path": item.component_path,
            "route_params": item.route_params or {},
            "keep_alive": bool(item.keep_alive),
            "create_time": item.create_time,
            "update_time": item.update_time,
        }

    def _serialize_router_node(
        self,
        node: AccessControlItem,
        children_map: Dict[Optional[int], List[AccessControlItem]],
        parent: Optional[AccessControlItem],
    ) -> Dict[str, Any]:
        child_nodes = children_map.get(node.id, [])
        route: Dict[str, Any] = {
            "name": self._resolve_route_name(node),
            "path": self._resolve_route_path(node, parent),
            "hidden": self._is_hidden(node),
            "component": self._resolve_component(node, parent, child_nodes),
            "meta": self._build_meta(node),
        }

        if child_nodes:
            route["children"] = [
                self._serialize_router_node(child, children_map, node) for child in child_nodes
            ]
            if len(route["children"]) > 1:
                route["alwaysShow"] = True
            route["redirect"] = "noRedirect"
        else:
            route["children"] = []

        # 移除值为 None 的键，避免响应出现 null 字段
        cleaned = {key: value for key, value in route.items() if value is not None}
        return cleaned

    def _resolve_route_name(self, node: AccessControlItem) -> str:
        for candidate in self._candidate_name_fields(node):
            slug = self._slugify(candidate)
            if slug:
                return f"{slug}{node.id}"
        return str(node.id)

    def _candidate_name_fields(self, node: AccessControlItem) -> Iterable[str]:
        yield node.component_path or ""
        yield node.route_path or ""
        yield node.name or ""

    def _slugify(self, value: str) -> str:
        if not value:
            return ""
        tokens = [segment for segment in re.split(r"[^0-9A-Za-z]+", value) if segment]
        return "".join(token.capitalize() for token in tokens)

    def _resolve_route_path(self, node: AccessControlItem, parent: Optional[AccessControlItem]) -> str:
        raw_path = (node.route_path or "").strip()
        if node.is_external and raw_path:
            return raw_path

        if parent is None:
            if not raw_path:
                return f"/{node.id}"
            if raw_path.startswith("/"):
                return raw_path
            return f"/{raw_path}"

        if not raw_path:
            return str(node.id)
        return raw_path.lstrip("/")

    def _resolve_component(
        self,
        node: AccessControlItem,
        parent: Optional[AccessControlItem],
        children: list[AccessControlItem],
    ) -> Optional[str]:
        component = (node.component_path or "").strip() or None
        if component:
            return component
        if node.is_external:
            return None
        if parent is None:
            return "Layout"
        if children:
            return "ParentView"
        return None

    def _build_meta(self, node: AccessControlItem) -> Dict[str, Any]:
        return {
            "title": node.name,
            "icon": node.icon,
            "noCache": not bool(node.keep_alive),
            "link": node.route_path if node.is_external else None,
        }

    def _is_hidden(self, node: AccessControlItem) -> bool:
        display = (node.display_status or "show").strip().lower()
        return display == "hidden"


access_control_service = AccessControlService()
