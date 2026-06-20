import time
from datetime import datetime
from collections import defaultdict
from celery.utils.log import get_task_logger
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.celery_app import celery_app
from app.core.database import SessionLocal
from app.models import Job, JobStatus, Transaction, JobSummary
from app.services.file_processor import FileProcessor
from app.services.ai_service import get_gemini_service

logger = get_task_logger(__name__)

DOMESTIC_BRANDS = ["swiggy", "ola", "irctc"]

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@celery_app.task(bind=True, name="app.tasks.process_job")
def process_job(self, job_id: int, file_path: str):
    logger.info(f"Starting job {job_id}")
    db = SessionLocal()
    
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return
            
        job.status = JobStatus.PROCESSING
        db.commit()

        # Step 1: Data Cleaning
        processor = FileProcessor()
        records, raw_count, clean_count = processor.parse_file(file_path)
        
        job.row_count_raw = raw_count
        job.row_count_clean = clean_count
        db.commit()

        # Insert cleaned transactions
        for r in records:
            txn = Transaction(
                job_id=job.id,
                txn_id=r["txn_id"],
                date=r["date"],
                merchant=r["merchant"],
                amount=r["amount"],
                currency=r["currency"],
                status=r["status"],
                category=r["category"],
                account_id=r["account_id"],
                notes=r["notes"]
            )
            db.add(txn)
        db.commit()

        # Step 2: Anomaly Detection
        # Calculate medians per account
        txns = db.query(Transaction).filter(Transaction.job_id == job.id).all()
        account_amounts = defaultdict(list)
        for t in txns:
            if t.account_id:
                account_amounts[t.account_id].append(t.amount)
                
        import statistics
        account_medians = {}
        for acc, amounts in account_amounts.items():
            if amounts:
                account_medians[acc] = statistics.median(amounts)

        anomaly_count = 0
        for t in txns:
            is_anomaly = False
            reasons = []

            # Rule 1: Amount > 3x median
            if t.account_id and t.account_id in account_medians:
                median = account_medians[t.account_id]
                if t.amount > 3 * median and median > 0:
                    is_anomaly = True
                    reasons.append(f"Amount {t.amount} exceeds 3x median {median}")

            # Rule 2: USD but domestic brand
            if t.currency == "USD" and t.merchant and t.merchant.lower() in DOMESTIC_BRANDS:
                is_anomaly = True
                reasons.append("USD currency for domestic brand")

            if is_anomaly:
                t.is_anomaly = True
                t.anomaly_reason = "; ".join(reasons)
                anomaly_count += 1
                
        db.commit()

        # Step 3: LLM Classification (Batched)
        gemini = get_gemini_service()
        uncategorized = db.query(Transaction).filter(
            Transaction.job_id == job.id, 
            Transaction.category == 'Uncategorised'
        ).all()

        if uncategorized:
            batch_size = 50
            for i in range(0, len(uncategorized), batch_size):
                batch = uncategorized[i:i + batch_size]
                prompt_data = [
                    {"id": str(t.id), "merchant": t.merchant, "amount": t.amount, "notes": t.notes}
                    for t in batch
                ]
                
                results = gemini.categorize_batch(prompt_data)
                
                for t in batch:
                    cat = results.get(str(t.id))
                    if cat:
                        t.llm_category = cat
                        t.category = cat
                    else:
                        t.llm_failed = True
            db.commit()

        # Step 4: LLM Narrative Summary
        total_inr = db.query(func.sum(Transaction.amount)).filter(Transaction.job_id == job.id, Transaction.currency == 'INR').scalar() or 0.0
        total_usd = db.query(func.sum(Transaction.amount)).filter(Transaction.job_id == job.id, Transaction.currency == 'USD').scalar() or 0.0
        
        top_merchants_query = db.query(
            Transaction.merchant, func.sum(Transaction.amount).label('total')
        ).filter(
            Transaction.job_id == job.id, 
            Transaction.merchant.isnot(None)
        ).group_by(Transaction.merchant).order_by(func.sum(Transaction.amount).desc()).limit(3).all()
        
        top_merchants = [m.merchant for m in top_merchants_query]

        stats_payload = {
            "total_spend_inr": float(total_inr),
            "total_spend_usd": float(total_usd),
            "top_merchants": top_merchants,
            "anomaly_count": anomaly_count
        }

        summary_data = gemini.generate_summary(stats_payload)
        
        summary = JobSummary(
            job_id=job.id,
            total_spend_inr=summary_data.get("total_spend_inr", 0.0),
            total_spend_usd=summary_data.get("total_spend_usd", 0.0),
            top_merchants=summary_data.get("top_merchants", []),
            anomaly_count=summary_data.get("anomaly_count", anomaly_count),
            narrative=summary_data.get("narrative", ""),
            risk_level=summary_data.get("risk_level", "low")
        )
        db.add(summary)

        # Mark as completed
        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"Job {job.id} completed successfully.")

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        db.rollback()
        if job:
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            db.commit()
    finally:
        db.close()
