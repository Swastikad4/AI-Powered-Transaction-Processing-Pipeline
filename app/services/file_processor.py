import pandas as pd
from typing import List, Dict, Any, Tuple
from datetime import datetime

class FileProcessingError(Exception):
    pass

class FileProcessor:
    def parse_file(self, file_path: str) -> Tuple[List[Dict[str, Any]], int, int]:
        """
        Parses the CSV, cleans it according to the rules, and returns records.
        Returns: (cleaned_records, raw_row_count, clean_row_count)
        """
        try:
            df = pd.read_csv(file_path)
            raw_count = len(df)
            
            # Remove exact duplicates
            df = df.drop_duplicates()
            
            records = []
            for _, row in df.iterrows():
                record = self._clean_row(row)
                if record:
                    records.append(record)
                    
            clean_count = len(records)
            return records, raw_count, clean_count
            
        except Exception as e:
            raise FileProcessingError(f"Failed to process file: {str(e)}")

    def _clean_row(self, row: pd.Series) -> Dict[str, Any]:
        """Cleans a single row according to the assignment rules."""
        # Date: Normalize to ISO 8601
        raw_date = row.get("date")
        clean_date = self._parse_date(raw_date)
        if not clean_date:
            return None # Skip if date is completely unparseable
            
        # Amount: Strip currency symbols
        raw_amount = str(row.get("amount", "0"))
        clean_amount = self._parse_amount(raw_amount)
        
        # Status: Uppercase
        raw_status = str(row.get("status", ""))
        clean_status = raw_status.upper() if raw_status and str(raw_status).lower() != "nan" else "PENDING"
        
        # Category: Fill missing with 'Uncategorised'
        raw_category = str(row.get("category", ""))
        clean_category = "Uncategorised" if not raw_category or str(raw_category).lower() == "nan" else raw_category.strip()
        
        # Currency: Uppercase if present
        raw_currency = str(row.get("currency", "INR"))
        clean_currency = raw_currency.upper() if raw_currency and str(raw_currency).lower() != "nan" else "INR"

        return {
            "txn_id": str(row.get("txn_id", "")) if pd.notna(row.get("txn_id")) else None,
            "date": clean_date,
            "merchant": str(row.get("merchant", "")) if pd.notna(row.get("merchant")) else None,
            "amount": clean_amount,
            "currency": clean_currency,
            "status": clean_status,
            "category": clean_category,
            "account_id": str(row.get("account_id", "")) if pd.notna(row.get("account_id")) else None,
            "notes": str(row.get("notes", "")) if pd.notna(row.get("notes")) else None,
        }

    def _parse_date(self, value: Any) -> datetime:
        if pd.isna(value):
            return None
        date_str = str(value).strip()
        
        # Try DD-MM-YYYY and YYYY/MM/DD
        formats = [
            "%d-%m-%Y",
            "%Y/%m/%d",
            "%Y-%m-%d",
            "%m/%d/%Y"
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
                
        try:
            return pd.to_datetime(date_str, dayfirst=True).to_pydatetime()
        except:
            return datetime.utcnow()

    def _parse_amount(self, value: str) -> float:
        val = value.replace("$", "").replace(",", "").strip()
        try:
            return float(val)
        except ValueError:
            return 0.0
