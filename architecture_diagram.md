# High-Level Visual Diagram

This diagram traces the exact path a single request takes from the API endpoint to data persistence and back, satisfying the "System Design & Data Flow" requirement for your video review.

```mermaid
sequenceDiagram
    participant User
    participant FastAPI (API)
    participant PostgreSQL (DB)
    participant Redis (Broker)
    participant Celery (Worker)
    participant Gemini AI (LLM)

    %% 1. Upload Flow
    User->>FastAPI (API): POST /jobs/upload (transactions.csv)
    FastAPI (API)->>FastAPI (API): Validate File
    FastAPI (API)->>PostgreSQL (DB): Create Job (status=pending)
    FastAPI (API)->>Redis (Broker): Enqueue process_job Task
    FastAPI (API)-->>User: Return job_id
    
    %% 2. Processing Flow
    Redis (Broker)->>Celery (Worker): Dequeue process_job Task
    Celery (Worker)->>PostgreSQL (DB): Update Job (status=processing)
    
    %% 2a. Data Cleaning
    Celery (Worker)->>Celery (Worker): Parse CSV, Normalize Dates, Strip Currency, Drop Duplicates
    Celery (Worker)->>PostgreSQL (DB): Bulk Insert Transactions
    
    %% 2b. Anomaly Detection
    Celery (Worker)->>PostgreSQL (DB): Query Historical Account Data
    PostgreSQL (DB)-->>Celery (Worker): Return Account txns
    Celery (Worker)->>Celery (Worker): Flag Anomalies (Amount > 3x Median, USD+Domestic)
    Celery (Worker)->>PostgreSQL (DB): Update Transactions (is_anomaly)

    %% 2c. Batched LLM Classification
    Celery (Worker)->>PostgreSQL (DB): Fetch Uncategorised Transactions
    PostgreSQL (DB)-->>Celery (Worker): List of Uncategorised txns
    Celery (Worker)->>Gemini AI (LLM): Request Categorization (Batched prompts of 50)
    Gemini AI (LLM)-->>Celery (Worker): JSON Array of Categories
    Celery (Worker)->>PostgreSQL (DB): Update Transactions (category)

    %% 2d. LLM Narrative Summary
    Celery (Worker)->>PostgreSQL (DB): Aggregate totals (INR, USD, Top Merchants, Anomaly Count)
    PostgreSQL (DB)-->>Celery (Worker): Aggregated Stats
    Celery (Worker)->>Gemini AI (LLM): Request Narrative & Risk Level (Single Prompt)
    Gemini AI (LLM)-->>Celery (Worker): JSON Summary Data
    Celery (Worker)->>PostgreSQL (DB): Insert JobSummary
    
    %% 2e. Completion
    Celery (Worker)->>PostgreSQL (DB): Update Job (status=completed)
    
    %% 3. Status Polling
    User->>FastAPI (API): GET /jobs/{job_id}/results
    FastAPI (API)->>PostgreSQL (DB): Query Job, JobSummary, and Transactions
    PostgreSQL (DB)-->>FastAPI (API): Structured Output Data
    FastAPI (API)-->>User: Return Full Job Results (JSON)
```

## Review Video Talking Points

1.  **The Blueprint:** Above is the request lifecycle. File goes to API -> Saved to DB as pending -> Task to Redis -> Celery picks up task -> File is parsed and cleaned in Python -> Inserted to DB -> Median anomalies calculated -> Uncategorised are sent to Gemini in a *single batched prompt* (to save rate limits/time) -> Summary is aggregated and sent to Gemini -> Job marked complete.
2.  **The "Why":** We use Celery+Redis because LLM calls are slow and can fail. A background job queue prevents the API from timing out and provides built-in exponential backoff retries for Gemini API limits. PostgreSQL is robust and relational, fitting financial data perfectly. FastAPI provides high-throughput async endpoints.
3.  **The Breaking Point (100x Scale):** If traffic scales 100x, the first bottleneck is parsing large CSVs entirely in memory within the Celery worker (OOM errors) and rate limits from the LLM provider.
4.  **The Next Iteration:** To fix the scale, I would:
    *   Stream the CSV to cloud storage (S3) instead of local disk.
    *   Use Pandas chunking or a stream parser (like Python's `csv` module row-by-row) to avoid memory spikes.
    *   Fan-out processing: have one Celery task parse the file and split it into chunks, spawning multiple smaller sub-tasks to process chunks in parallel.
