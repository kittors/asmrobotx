"""日志相关的响应与请求模型。"""

from typing import Optional

from pydantic import BaseModel

from app.api.v1.schemas.common import ResponseEnvelope


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
