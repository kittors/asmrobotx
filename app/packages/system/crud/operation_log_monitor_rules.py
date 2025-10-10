"""操作日志监控规则的数据库访问封装。"""

from __future__ import annotations

from typing import Optional, Tuple
import re

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
        """返回与请求最匹配的监控规则。

        支持两类匹配：
        - exact：精确匹配；当规则 URI 中包含 `{param}` 形式的段时，按模板匹配单段路径
          （例如 `/a/{id}` 可匹配 `/a/123`，仅对 path 生效，忽略查询串）。
        - prefix：前缀匹配；当规则 URI 中包含 `{param}` 段时，会匹配以该模板为起始的更长路径
          （例如 `/a/{id}` 可匹配 `/a/123/edit`）。

        为避免误判，模板匹配仅在规则 URI 本身含有花括号时启用；其余情况沿用原有的
        字符串等值/startswith 判断。
        """

        if not request_uri:
            return None

        normalized_method = (http_method or "ALL").upper()
        candidates = (
            self.query(db)
            .filter(
                or_(
                    self.model.http_method == normalized_method,
                    self.model.http_method == "ALL",
                ),
            )
            .all()
        )

        # 仅用于模板匹配：从请求 URI 中剥离查询串，仅保留 path 用于与模板匹配
        path_only = request_uri.split("?", 1)[0]

        # Ranking tuple shape:
        # (
        #   mode_score,         # exact(2) > prefix(1)
        #   literal_score,      # literal path(2) > template with {param}(1)
        #   method_score,       # exact method(2) > ALL(1)
        #   length_score,       # longer patterns are more specific
        #   rule_id             # stable tie-breaker: higher id wins (newer rule)
        # )
        best_match: Optional[Tuple[Tuple[int, int, int, int, int], OperationLogMonitorRule]] = None
        for rule in candidates:
            is_template = "{" in rule.request_uri and "}" in rule.request_uri

            if rule.match_mode == "exact":
                if is_template:
                    # 模板精确匹配：必须与规则模板在 path 维度上完全一致
                    pattern = self._compile_path_template(rule.request_uri, exact=True)
                    matched = bool(pattern.fullmatch(path_only))
                else:
                    matched = request_uri == rule.request_uri
                mode_score = 2
            else:  # prefix
                if is_template:
                    # 模板前缀匹配：允许在模板后出现更长的路径（例如子资源）
                    pattern = self._compile_path_template(rule.request_uri, exact=False)
                    matched = bool(pattern.match(path_only))
                else:
                    matched = request_uri.startswith(rule.request_uri)
                mode_score = 1

            if not matched:
                continue

            # 更偏向非模板（字面量）规则，避免诸如 `/a/{id}` 抢占 `/a/routers` 的匹配权
            literal_score = 2 if not is_template else 1
            method_score = 2 if rule.http_method == normalized_method else 1
            length_score = len(rule.request_uri)

            current_rank = (mode_score, literal_score, method_score, length_score, rule.id)
            if best_match is None or current_rank > best_match[0]:
                best_match = (current_rank, rule)

        return best_match[1] if best_match else None

    @staticmethod
    def _compile_path_template(template: str, *, exact: bool) -> re.Pattern[str]:
        """将形如 "/a/{id}/b" 的模板转为正则。

        - `{name}` 会被视为单段匹配 `[^/]+`
        - 其它字符会被按字面转义
        - exact=True 时，整体采用 `^...$`；否则采用 `^...(?:/.*)?$` 以支持前缀扩展
        - 仅匹配 path，不包含查询参数
        """

        # 将模板分段处理，避免误伤 '/'
        parts = template.split("/")
        regex_parts: list[str] = []
        for part in parts:
            if not part:
                regex_parts.append("")
                continue
            if part.startswith("{") and part.endswith("}") and len(part) >= 3:
                # 使用非捕获命名也可，但此处仅需匹配，不使用参数值
                regex_parts.append(r"[^/]+")
            else:
                regex_parts.append(re.escape(part))

        core = "/".join(regex_parts)
        if exact:
            pattern = f"^{core}$"
        else:
            # 允许在模板后跟任意更深层级
            pattern = f"^{core}(?:/.*)?$"
        return re.compile(pattern)

    def list_disabled_rules(self, db: Session) -> list[OperationLogMonitorRule]:
        """列出所有显式禁用的监听规则。"""

        return self.query(db).filter(self.model.is_enabled.is_(False)).all()

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

        query = self.query(db)

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

        query = self.query(db).filter(
            self.model.request_uri == request_uri,
            self.model.http_method == http_method,
            self.model.match_mode == match_mode,
        )

        if exclude_id is not None:
            query = query.filter(self.model.id != exclude_id)

        return query.first()


operation_log_monitor_rule_crud = OperationLogMonitorRuleCRUD(OperationLogMonitorRule)
