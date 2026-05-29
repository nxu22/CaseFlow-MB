"""
Case-related request/response schemas.

Design decisions (interview talking points):
1. CaseCreate 要求 client_id（案件必须属于某个客户）；assigned_lawyer_id 可选
   （案件可以先建后分配律师）。case_number 不在 Create 里——它由后端自动生成，
   不让前端控制，避免重复和格式混乱。
2. CaseUpdate 全字段 Optional（PATCH 部分更新）；client_id 不可改
   （案件归属客户一旦确定不应随意变更，这是业务约束）。
3. status 用 CaseStatus 枚举，Pydantic 自动校验非法值。
"""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from models.case import CaseStatus


class CaseCreate(BaseModel):
    """Input for creating a case. client_id 必填。"""
    client_id: uuid.UUID
    assigned_lawyer_id: Optional[uuid.UUID] = None
    status: CaseStatus = CaseStatus.OPEN  # 新案件默认 open
    violation_type: Optional[str] = Field(default=None, max_length=255)
    violation_date: Optional[date] = None
    fine_amount: Optional[Decimal] = Field(default=None, ge=0)  # 罚款不能为负
    court_date: Optional[date] = None
    description: Optional[str] = None


class CaseUpdate(BaseModel):
    """
    Input for PATCH. 全字段 Optional。
    注意：没有 client_id —— 案件归属客户不可通过 PATCH 变更。
    """
    assigned_lawyer_id: Optional[uuid.UUID] = None
    status: Optional[CaseStatus] = None
    violation_type: Optional[str] = Field(default=None, max_length=255)
    violation_date: Optional[date] = None
    fine_amount: Optional[Decimal] = Field(default=None, ge=0)
    court_date: Optional[date] = None
    description: Optional[str] = None
    ai_summary: Optional[str] = None  # Day 2 AI 功能会写这个字段


class CaseResponse(BaseModel):
    """Output for any endpoint returning a case."""
    id: uuid.UUID
    case_number: str
    client_id: uuid.UUID
    assigned_lawyer_id: Optional[uuid.UUID] = None
    status: CaseStatus
    violation_type: Optional[str] = None
    violation_date: Optional[date] = None
    fine_amount: Optional[Decimal] = None
    court_date: Optional[date] = None
    description: Optional[str] = None
    ai_summary: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
