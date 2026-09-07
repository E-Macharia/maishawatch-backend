# app/services/export_service.py
import json
import csv
from datetime import datetime, timezone
from typing import List, Dict
from app.core.db import db


class ExportService:
    """Export conversation history"""

    @staticmethod
    def export_to_json(conversation_id: str, messages: List[Dict]) -> str:
        """Export conversation to JSON"""
        export_data = {
            "conversation_id": conversation_id,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "messages": messages,
        }
        return json.dumps(export_data, indent=2)

    @staticmethod
    def export_to_csv(messages: List[Dict]) -> str:
        """Export conversation to CSV"""
        import io

        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow(["Role", "Content", "Action", "Created At"])

        # Data
        for msg in messages:
            writer.writerow(
                [
                    msg.get("role", ""),
                    msg.get("content", ""),
                    msg.get("action", ""),
                    msg.get("created_at", ""),
                ]
            )

        return output.getvalue()

    @staticmethod
    def export_to_pdf(conversation_id: str, messages: List[Dict]) -> bytes:
        """Export conversation to PDF"""
        # This requires reportlab or similar library
        # For now, return JSON as fallback
        import json

        return json.dumps(
            {
                "conversation_id": conversation_id,
                "messages": messages,
                "note": "PDF export requires additional library (reportlab)",
            }
        ).encode()
