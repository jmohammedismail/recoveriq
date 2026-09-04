"""
RecoverIQ - Payment File Ingestion & AI Analysis Pipeline
Coordinates file extraction, schema normalization, strict validation,
deduplication, programmatic totals calculation, and AI analysis context.
"""

import base64
import logging
from typing import Dict, Any, List, Optional

from .schema import normalize_record
from .extractors import (
    extract_csv,
    extract_xlsx,
    extract_json,
    extract_txt,
    extract_pdf,
    extract_docx
)

logger = logging.getLogger("recoveriq.ingestion")
logger.setLevel(logging.INFO)


class IngestionPipeline:
    """
    Main orchestration class for ingesting payment data files
    (CSV, XLSX, JSON, TXT, PDF, DOCX).
    """

    @staticmethod
    def process_file(
        filename: str,
        content_str: Optional[str] = None,
        file_bytes: Optional[bytes] = None
    ) -> Dict[str, Any]:
        """
        Parses, normalizes, validates, and calculates metrics from an uploaded payment file.
        """
        fname = filename or "uploaded_payments.csv"
        ext = fname.lower().split(".")[-1] if "." in fname else "csv"

        # Decode base64 bytes if content_str is data URI or base64
        if not file_bytes and content_str and content_str.startswith("data:"):
            try:
                header, encoded = content_str.split(",", 1)
                file_bytes = base64.b64decode(encoded)
            except Exception:
                pass

        if not file_bytes and content_str:
            try:
                # If bytes required for binary formats (pdf, docx, xlsx)
                file_bytes = content_str.encode("utf-8", errors="ignore")
            except Exception:
                file_bytes = b""

        # 1. Extraction Layer
        raw_records: List[Dict[str, Any]] = []

        if ext == "csv":
            raw_records = extract_csv(content_str or (file_bytes.decode("utf-8", errors="ignore") if file_bytes else ""))
        elif ext in ("xlsx", "xls"):
            raw_records = extract_xlsx(file_bytes or b"")
        elif ext == "json":
            raw_records = extract_json(content_str or (file_bytes.decode("utf-8", errors="ignore") if file_bytes else ""))
        elif ext == "txt":
            raw_records = extract_txt(content_str or (file_bytes.decode("utf-8", errors="ignore") if file_bytes else ""))
        elif ext == "pdf":
            raw_records = extract_pdf(file_bytes or b"", content_str=content_str)
        elif ext in ("docx", "doc"):
            raw_records = extract_docx(file_bytes or b"")
        else:
            # Fallback: try CSV first, then TXT
            raw_str = content_str or (file_bytes.decode("utf-8", errors="ignore") if file_bytes else "")
            raw_records = extract_csv(raw_str)
            if not raw_records:
                raw_records = extract_txt(raw_str)

        # 2. Normalization & Deduplication Layer
        seen_pids = set()
        valid_records: List[Dict[str, Any]] = []
        invalid_diagnostics: List[Dict[str, Any]] = []
        duplicates_removed = 0

        for raw_item in raw_records:
            norm_item, err = normalize_record(raw_item)
            if err:
                invalid_diagnostics.append({"raw": raw_item, "error": err})
                continue

            pid = norm_item["payment_id"]
            if pid in seen_pids:
                duplicates_removed += 1
                continue

            seen_pids.add(pid)
            valid_records.append(norm_item)

        # 3. Programmatic Metric Calculation Layer (No AI fabrication)
        total_records_found = len(valid_records)
        failed_records = [r for r in valid_records if r.get("is_failed", True)]
        successful_records = [r for r in valid_records if r.get("status") == "SUCCESS" or not r.get("is_failed", True)]
        pending_records = [r for r in valid_records if r.get("status") == "PENDING"]

        failed_count = len(failed_records)
        successful_count = len(successful_records)
        pending_count = len(pending_records)

        money_at_risk = sum(r["amount"] for r in failed_records)
        total_dataset_amount = sum(r["amount"] for r in valid_records)

        potentially_recoverable = sum(
            r["amount"] for r in valid_records
            if r.get("recovery_eligible", False) or r.get("recommended_action") in ("AUTO_RECOVERY", "ALREADY_RECOVERED")
            or "auto" in str(r.get("ai_recommendation", "")).lower()
        )
        recovered_amount = sum(
            r["amount"] for r in valid_records
            if r.get("recommended_action") == "ALREADY_RECOVERED" or "already recovered" in str(r.get("ai_recommendation", "")).lower()
        )
        recovery_rate = round((recovered_amount / total_dataset_amount * 100), 2) if total_dataset_amount > 0 else 0.0

        # 4. Debug Logging
        print(f"FILE: {fname}")
        print(f"EXTRACTION: raw records detected: {len(raw_records)}")
        print(f"NORMALIZATION: records created: {len(valid_records) + len(invalid_diagnostics) + duplicates_removed}")
        print(f"VALIDATION: valid: {len(valid_records)}, invalid: {len(invalid_diagnostics)}, duplicates removed: {duplicates_removed}")
        print(f"AI INPUT: {len(valid_records)} payment records | Failed: {failed_count} | Success: {successful_count} | Money at risk: Rs {money_at_risk}")

        return {
            "success": True,
            "file_name": fname,
            "filename": fname,
            "records_found": total_records_found,
            "total_records": total_records_found,
            "valid_records": len(valid_records),
            "invalid_records": len(invalid_diagnostics),
            "failed_payments": failed_count,
            "failed_count": failed_count,
            "successful_payments": successful_count,
            "healthy_payments": successful_count,
            "pending_payments": pending_count,
            "money_at_risk": money_at_risk,
            "total_at_risk": money_at_risk,
            "total_dataset_amount": total_dataset_amount,
            "potentially_recoverable": potentially_recoverable,
            "recovered_amount": recovered_amount,
            "recovery_rate": recovery_rate,
            "duplicates_removed": duplicates_removed,
            "payments": valid_records,
            "records": valid_records,
            "diagnostics": invalid_diagnostics
        }
