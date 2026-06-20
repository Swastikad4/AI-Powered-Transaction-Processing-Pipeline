import os
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.config import get_settings
from app.core.database import get_db
from app.core.logging import get_logger
from app.models import Job, JobStatus, Transaction, JobSummary
from app.schemas import (
    JobUploadResponse,
    JobStatusResponse,
    JobResultResponse,
    JobListResponse,
    JobListItem,
    JobSummaryResponse,
    TransactionResultResponse
)
from app.tasks import process_job

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/upload", response_model=JobUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed.")
        
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    upload_dir = settings.upload_path
    unique_name = f"{uuid.uuid4().hex}.csv"
    file_path = upload_dir / unique_name

    with open(file_path, "wb") as f:
        f.write(content)

    job = Job(
        filename=file.filename,
        status=JobStatus.PENDING,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Enqueue task
    process_job.delay(job.id, str(file_path))

    return JobUploadResponse(
        job_id=job.id,
        message="File uploaded successfully. Processing started."
    )


@router.get("/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    summary_response = None
    if job.summary:
        summary_response = JobSummaryResponse(
            total_spend_inr=job.summary.total_spend_inr,
            total_spend_usd=job.summary.total_spend_usd,
            top_merchants=job.summary.top_merchants or [],
            anomaly_count=job.summary.anomaly_count,
            narrative=job.summary.narrative or "",
            risk_level=job.summary.risk_level or "low"
        )

    return JobStatusResponse(
        job_id=job.id,
        status=job.status.value if hasattr(job.status, 'value') else str(job.status),
        filename=job.filename,
        created_at=job.created_at,
        error_message=job.error_message,
        summary=summary_response
    )


@router.get("/{job_id}/results", response_model=JobResultResponse)
async def get_job_results(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Job is not completed yet.")

    summary_response = None
    if job.summary:
        summary_response = JobSummaryResponse(
            total_spend_inr=job.summary.total_spend_inr,
            total_spend_usd=job.summary.total_spend_usd,
            top_merchants=job.summary.top_merchants or [],
            anomaly_count=job.summary.anomaly_count,
            narrative=job.summary.narrative or "",
            risk_level=job.summary.risk_level or "low"
        )

    txns = db.query(Transaction).filter(Transaction.job_id == job_id).all()
    transactions_response = [
        TransactionResultResponse(
            txn_id=t.txn_id,
            date=t.date,
            merchant=t.merchant,
            amount=t.amount,
            currency=t.currency,
            status=t.status,
            category=t.category,
            account_id=t.account_id,
            is_anomaly=t.is_anomaly,
            anomaly_reason=t.anomaly_reason,
            llm_category=t.llm_category
        )
        for t in txns
    ]

    return JobResultResponse(
        job_id=job.id,
        status=job.status.value if hasattr(job.status, 'value') else str(job.status),
        summary=summary_response,
        transactions=transactions_response
    )


@router.get("", response_model=JobListResponse)
async def list_jobs(
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(Job)
    if status:
        query = query.filter(Job.status == status)
    
    total = query.count()
    jobs = query.order_by(desc(Job.created_at)).all()

    items = [
        JobListItem(
            job_id=j.id,
            status=j.status.value if hasattr(j.status, 'value') else str(j.status),
            filename=j.filename,
            row_count_raw=j.row_count_raw,
            created_at=j.created_at
        )
        for j in jobs
    ]

    return JobListResponse(jobs=items, total=total)
