"""组织相关业务逻辑：提供树形结构输出。"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.packages.system.core.constants import HTTP_STATUS_OK
from app.packages.system.core.responses import create_response
from app.packages.system.crud.organizations import organization_crud
from app.packages.system.models.organization import Organization


class OrganizationService:
    """封装组织的树形查询。"""

    def list_tree(self, db: Session) -> dict[str, Any]:
        """返回组织的树形结构，按 `sort_order, id` 排序。"""

        # 全量加载后在内存中组装树，规模通常较小
        items: List[Organization] = organization_crud.list_all(db)
        if not items:
            return create_response("获取组织树成功", [], HTTP_STATUS_OK)

        children_map: Dict[Optional[int], List[Organization]] = defaultdict(list)
        for item in items:
            children_map[item.parent_id].append(item)

        # 同级排序：sort_order -> id
        for siblings in children_map.values():
            siblings.sort(key=lambda n: (n.sort_order, n.id))

        def build(node: Organization) -> Dict[str, Any]:
            return {
                "org_id": node.id,
                "org_name": node.name,
                "parent_id": node.parent_id,
                "sort_order": node.sort_order,
                "children": [build(child) for child in children_map.get(node.id, [])],
            }

        roots = [build(root) for root in children_map.get(None, [])]
        return create_response("获取组织树成功", roots, HTTP_STATUS_OK)


organization_service = OrganizationService()

