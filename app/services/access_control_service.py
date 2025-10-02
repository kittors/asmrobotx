"""访问控制相关的业务逻辑封装。"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional

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

            return {
                "id": node.id,
                "parent_id": node.parent_id,
                "name": node.name,
                "type": node.type,
                "icon": node.icon,
                "is_external": bool(node.is_external),
                "permission_code": node.permission_code,
                "route_path": node.route_path,
                "display_status": display_status,
                "enabled_status": enabled_status_value,
                "effective_display_status": effective_display,
                "effective_enabled_status": effective_enabled,
                "sort_order": node.sort_order,
                "children": children_payload,
            }

        tree = [
            build_node(root, None, None)
            for root in filtered_roots
            if include_map.get(root.id, False)
        ]
        return create_response("获取访问控制列表成功", tree, HTTP_STATUS_OK)

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

        if parent_id is not None:
            parent = access_control_crud.get(db, parent_id)
            if parent is None:
                raise AppException("上级访问控制项不存在", HTTP_STATUS_NOT_FOUND)
            if parent.type == AccessControlTypeEnum.BUTTON.value:
                raise AppException("按钮类型不允许继续添加子项", HTTP_STATUS_BAD_REQUEST)

        node_type = payload.get("type")
        if node_type is None:
            raise AppException("访问控制项类型必填", HTTP_STATUS_BAD_REQUEST)

        if parent is None and node_type != AccessControlTypeEnum.DIRECTORY.value:
            raise AppException("根节点必须是目录类型", HTTP_STATUS_BAD_REQUEST)

        if parent is not None:
            if node_type == AccessControlTypeEnum.DIRECTORY.value:
                raise AppException("目录类型仅支持作为根节点存在", HTTP_STATUS_BAD_REQUEST)
            if parent.type == AccessControlTypeEnum.DIRECTORY.value and node_type not in {
                AccessControlTypeEnum.MENU.value,
                AccessControlTypeEnum.BUTTON.value,
            }:
                raise AppException("目录下仅支持菜单或按钮类型", HTTP_STATUS_BAD_REQUEST)
            if parent.type == AccessControlTypeEnum.MENU.value and node_type not in {
                AccessControlTypeEnum.MENU.value,
                AccessControlTypeEnum.BUTTON.value,
            }:
                raise AppException("菜单下仅支持子菜单或按钮类型", HTTP_STATUS_BAD_REQUEST)

        name_value = self._normalize_name(payload.get("name"))
        if not name_value:
            raise AppException("名称必填", HTTP_STATUS_BAD_REQUEST)

        permission_code = payload.get("permission_code")
        if not permission_code:
            raise AppException("权限字符必填", HTTP_STATUS_BAD_REQUEST)

        self._ensure_unique_permission_code(db, permission_code)

        self._validate_route_and_display(node_type, payload)

        if node_type == AccessControlTypeEnum.BUTTON.value:
            payload["is_external"] = False

        enabled_status_value = payload.get("enabled_status")
        display_status_value = payload.get("display_status")
        route_path_value = payload.get("route_path")

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

        permission_code = payload.get("permission_code")
        if not permission_code:
            raise AppException("权限字符必填", HTTP_STATUS_BAD_REQUEST)
        self._ensure_unique_permission_code(db, permission_code, exclude_id=db_obj.id)

        self._validate_route_and_display(db_obj.type, payload)

        if db_obj.type == AccessControlTypeEnum.BUTTON.value:
            payload["is_external"] = False

        route_path_value = payload.get("route_path")

        db_obj.name = name_value
        if "icon" in payload:
            db_obj.icon = payload["icon"]
        if "is_external" in payload:
            db_obj.is_external = bool(payload["is_external"])
        db_obj.permission_code = permission_code
        if "route_path" in payload:
            db_obj.route_path = route_path_value
        if "display_status" in payload:
            db_obj.display_status = payload["display_status"]
        if "enabled_status" in payload:
            db_obj.enabled_status = payload["enabled_status"]
        if "sort_order" in payload:
            db_obj.sort_order = payload["sort_order"]

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

    def reorder(
        self,
        db: Session,
        *,
        item_id: int,
        target_parent_id: Optional[int],
        target_index: int,
    ) -> dict[str, Any]:
        """调整访问控制项的父级与排序位置。"""

        if target_index < 0:
            raise AppException("目标排序位置无效", HTTP_STATUS_BAD_REQUEST)

        item = access_control_crud.get(db, item_id)
        if item is None:
            raise AppException("访问控制项不存在", HTTP_STATUS_NOT_FOUND)

        normalized_parent_id = self._normalize_parent_id(target_parent_id)

        if normalized_parent_id == item.id:
            raise AppException("无法将节点移动到自身", HTTP_STATUS_BAD_REQUEST)

        parent = None
        if normalized_parent_id is not None:
            parent = access_control_crud.get(db, normalized_parent_id)
            if parent is None:
                raise AppException("目标父级不存在", HTTP_STATUS_NOT_FOUND)

        self._validate_move(item, parent)

        if parent is not None:
            self._ensure_no_cycle(item, parent)

        old_parent_id = item.parent_id

        # 先重新排序旧父级下的兄弟节点，移除当前节点
        self._resequence_siblings(db, old_parent_id, excluding_id=item.id)

        # 更新父级
        item.parent_id = normalized_parent_id

        # 将节点插入目标父级的指定位置
        self._insert_into_target(db, item, parent, target_index)

        db.commit()
        db.refresh(item)
        data = self._serialize_item(item)
        return create_response("更新排序成功", data, HTTP_STATUS_OK)

    def _ensure_unique_permission_code(
        self,
        db: Session,
        permission_code: str,
        *,
        exclude_id: Optional[int] = None,
    ) -> None:
        existing = access_control_crud.get_by_permission_code(
            db,
            permission_code,
            exclude_id=exclude_id,
        )
        if existing is not None:
            raise AppException("权限字符已存在", HTTP_STATUS_CONFLICT)

    def _validate_route_and_display(self, node_type: str, payload: Dict[str, Any]) -> None:
        if node_type in {AccessControlTypeEnum.DIRECTORY.value, AccessControlTypeEnum.MENU.value}:
            route_path = payload.get("route_path")
            display_status = payload.get("display_status")
            enabled_status = payload.get("enabled_status")
            normalized_route = self._normalize_route_path(route_path)
            if not normalized_route:
                raise AppException("目录或菜单类型必须提供路由地址", HTTP_STATUS_BAD_REQUEST)
            payload["route_path"] = normalized_route
            payload["display_status"] = self._normalize_display_status(display_status)
            payload["enabled_status"] = self._normalize_enabled_status_value(enabled_status)
        else:
            payload["enabled_status"] = self._normalize_enabled_status_value(payload.get("enabled_status"))
            if "display_status" in payload and payload["display_status"] is not None:
                payload["display_status"] = self._normalize_display_status(payload["display_status"])
            if "route_path" in payload:
                payload["route_path"] = self._normalize_route_path(payload["route_path"])

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

    def _normalize_parent_id(self, parent_id: Optional[int]) -> Optional[int]:
        if parent_id in (0, "0"):
            return None
        return parent_id

    def _validate_move(self, item: AccessControlItem, parent: Optional[AccessControlItem]) -> None:
        if parent is None:
            if item.type != AccessControlTypeEnum.DIRECTORY.value:
                raise AppException("仅目录类型可以作为顶层节点", HTTP_STATUS_BAD_REQUEST)
            return

        if parent.type == AccessControlTypeEnum.BUTTON.value:
            raise AppException("按钮类型不允许拥有下级节点", HTTP_STATUS_BAD_REQUEST)

        if item.type == AccessControlTypeEnum.DIRECTORY.value:
            raise AppException("目录类型仅能存在于顶层", HTTP_STATUS_BAD_REQUEST)

        if item.type == AccessControlTypeEnum.MENU.value and parent.type not in {
            AccessControlTypeEnum.DIRECTORY.value,
            AccessControlTypeEnum.MENU.value,
        }:
            raise AppException("菜单只能移动到目录或菜单下", HTTP_STATUS_BAD_REQUEST)

        if item.type == AccessControlTypeEnum.BUTTON.value and parent.type not in {
            AccessControlTypeEnum.DIRECTORY.value,
            AccessControlTypeEnum.MENU.value,
        }:
            raise AppException("按钮只能移动到目录或菜单下", HTTP_STATUS_BAD_REQUEST)

    def _ensure_no_cycle(self, item: AccessControlItem, parent: AccessControlItem) -> None:
        current = parent
        while current is not None:
            if current.id == item.id:
                raise AppException("不能将节点移动到其子节点下", HTTP_STATUS_BAD_REQUEST)
            current = current.parent

    def _resequence_siblings(
        self,
        db: Session,
        parent_id: Optional[int],
        *,
        excluding_id: Optional[int] = None,
    ) -> None:
        if parent_id is None:
            query = db.query(AccessControlItem).filter(AccessControlItem.parent_id.is_(None))
        else:
            query = db.query(AccessControlItem).filter(AccessControlItem.parent_id == parent_id)

        if hasattr(AccessControlItem, "is_deleted"):
            query = query.filter(AccessControlItem.is_deleted.is_(False))

        siblings = query.order_by(AccessControlItem.sort_order, AccessControlItem.id).all()
        filtered = [s for s in siblings if excluding_id is None or s.id != excluding_id]
        for index, sibling in enumerate(filtered):
            sibling.sort_order = index

    def _insert_into_target(
        self,
        db: Session,
        item: AccessControlItem,
        parent: Optional[AccessControlItem],
        target_index: int,
    ) -> None:
        if parent is None:
            query = db.query(AccessControlItem).filter(AccessControlItem.parent_id.is_(None))
        else:
            query = db.query(AccessControlItem).filter(AccessControlItem.parent_id == parent.id)

        if hasattr(AccessControlItem, "is_deleted"):
            query = query.filter(AccessControlItem.is_deleted.is_(False))

        siblings = [s for s in query.order_by(AccessControlItem.sort_order, AccessControlItem.id).all() if s.id != item.id]

        insert_index = min(target_index, len(siblings))
        siblings.insert(insert_index, item)

        for index, sibling in enumerate(siblings):
            sibling.sort_order = index

    def _serialize_item(self, item: AccessControlItem) -> Dict[str, Any]:
        return {
            "id": item.id,
            "parent_id": item.parent_id,
            "name": item.name,
            "type": item.type,
            "icon": item.icon,
            "is_external": bool(item.is_external),
            "permission_code": item.permission_code,
            "route_path": item.route_path,
            "display_status": item.display_status,
            "enabled_status": item.enabled_status,
            "sort_order": item.sort_order,
            "create_time": item.create_time,
            "update_time": item.update_time,
        }


access_control_service = AccessControlService()
