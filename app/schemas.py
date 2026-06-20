from typing import List, Optional, Any, Dict
from pydantic import BaseModel, ConfigDict
from datetime import datetime


class JobUploadResponse(BaseModel):
    job_id: int
    message: str


class JobSummaryResponse(BaseModel):
    total_spend_inr: float
    total_spend_usd: float
    top_merchants: List[str]
    anomaly_count: int
    narrative: str
    risk_level: str
    model_config = ConfigDict(from_attributes=True)


class JobStatusResponse(BaseModel):
    job_id: int
    status: str
    filename: str
    created_at: datetime
    error_message: Optional[str] = None
    summary: Optional[JobSummaryResponse] = None
    model_config = ConfigDict(from_attributes=True)


class TransactionResultResponse(BaseModel):
    txn_id: Optional[str] = None
    date: datetime
    merchant: Optional[str] = None
    amount: float
    currency: Optional[str] = None
    status: Optional[str] = None
    category: Optional[str] = None
    account_id: Optional[str] = None
    is_anomaly: bool
    anomaly_reason: Optional[str] = None
    llm_category: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class JobResultResponse(BaseModel):
    job_id: int
    status: str
    summary: Optional[JobSummaryResponse] = None
    transactions: List[TransactionResultResponse]
    model_config = ConfigDict(from_attributes=True)


class JobListItem(BaseModel):
    job_id: int
    status: str
    filename: str
    row_count_raw: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class JobListResponse(BaseModel):
    jobs: List[JobListItem]
    total: int
