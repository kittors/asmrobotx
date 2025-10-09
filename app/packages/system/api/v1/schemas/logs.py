"""日志相关的响应与请求模型。"""

from typing import Optional

from pydantic import BaseModel

from app.packages.system.api.v1.schemas.common import ResponseEnvelope


class OperationLogListItem(BaseModel):
    log_number: str
    module: str
    operation_type: str
    operation_type_code: str
    operator_name: str
    operator_ip: Optional[str]
    request_uri: Optional[str]
    status: str
    status_code: str
    operate_time: Optional[str]
    cost_ms: int


class OperationLogListData(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[OperationLogListItem]


class OperationLogLoginInfo(BaseModel):
    username: str
    department: Optional[str]
    ip_address: Optional[str]
    location: Optional[str]


class OperationLogRequestInfo(BaseModel):
    method: Optional[str]
    uri: Optional[str]


class OperationLogModuleInfo(BaseModel):
    module: Optional[str]
    operation_type: str
    operation_type_code: Optional[str]


class OperationLogDetailData(BaseModel):
    log_number: str
    login_info: OperationLogLoginInfo
    request_info: OperationLogRequestInfo
    operation_module: OperationLogModuleInfo
    class_method: Optional[str]
    request_params: str
    response_params: str
    status: str
    status_code: str
    cost_ms: int
    operate_time: Optional[str]
    error_message: Optional[str]


class LoginLogItem(BaseModel):
    visit_number: str
    username: str
    client_name: Optional[str]
    device_type: Optional[str]
    ip_address: Optional[str]
    login_location: Optional[str]
    operating_system: Optional[str]
    browser: Optional[str]
    status: str
    status_code: str
    message: Optional[str]
    login_time: Optional[str]


class LoginLogListData(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[LoginLogItem]


OperationLogListResponse = ResponseEnvelope[OperationLogListData]
OperationLogDetailResponse = ResponseEnvelope[OperationLogDetailData]
OperationLogDeletionResponse = ResponseEnvelope[Optional[dict]]
LoginLogListResponse = ResponseEnvelope[LoginLogListData]
LoginLogDeletionResponse = ResponseEnvelope[Optional[dict]]


class MonitorRuleBase(BaseModel):
    name: Optional[str] = None
    request_uri: Optional[str] = None
    http_method: Optional[str] = None
    match_mode: Optional[str] = None
    is_enabled: Optional[bool] = None
    description: Optional[str] = None
    operation_type_code: Optional[str] = None


class MonitorRuleCreate(MonitorRuleBase):
    request_uri: str


class MonitorRuleUpdate(MonitorRuleBase):
    pass


class MonitorRuleData(BaseModel):
    id: int
    name: Optional[str]
    request_uri: str
    http_method: str
    match_mode: str
    is_enabled: bool
    description: Optional[str]
    operation_type_code: Optional[str]
    operation_type_label: Optional[str]
    create_time: Optional[str]
    update_time: Optional[str]


class MonitorRuleListData(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[MonitorRuleData]


MonitorRuleListResponse = ResponseEnvelope[MonitorRuleListData]
MonitorRuleDetailResponse = ResponseEnvelope[MonitorRuleData]
MonitorRuleDeletionResponse = ResponseEnvelope[Optional[dict]]
