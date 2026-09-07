# app/services/language_service.py
from typing import Dict, List
import json


class LanguageService:
    """Multi-language support for chat"""

    TRANSLATIONS = {
        "en": {
            "greeting": "Hello {name}! 👋",
            "help": "How can I help you?",
            "equipment_status": "Equipment Status",
            "predictions": "Predictions",
            "alerts": "Alerts",
            "maintenance": "Maintenance",
            "reports": "Reports",
            "no_equipment": "No equipment found",
            "critical": "Critical",
            "high": "High",
            "medium": "Medium",
            "low": "Low",
            "operational": "Operational",
            "maintenance_needed": "Maintenance Needed",
            "decommissioned": "Decommissioned",
        },
        "sw": {
            "greeting": "Habari {name}! 👋",
            "help": "Ninaweza kukusaidiaje?",
            "equipment_status": "Hali ya Vifaa",
            "predictions": "Utabiri",
            "alerts": "Tahadhari",
            "maintenance": "Matengenezo",
            "reports": "Ripoti",
            "no_equipment": "Hakuna vifaa vilivyopatikana",
            "critical": "Muhimu Sana",
            "high": "Juu",
            "medium": "Wastani",
            "low": "Chini",
            "operational": "Inafanya Kazi",
            "maintenance_needed": "Inahitaji Matengenezo",
            "decommissioned": "Imeondolewa",
        },
        "fr": {
            "greeting": "Bonjour {name}! 👋",
            "help": "Comment puis-je vous aider?",
            "equipment_status": "Statut des Équipements",
            "predictions": "Prédictions",
            "alerts": "Alertes",
            "maintenance": "Maintenance",
            "reports": "Rapports",
            "no_equipment": "Aucun équipement trouvé",
            "critical": "Critique",
            "high": "Élevé",
            "medium": "Moyen",
            "low": "Faible",
            "operational": "Opérationnel",
            "maintenance_needed": "Maintenance Nécessaire",
            "decommissioned": "Mis Hors Service",
        },
    }

    @staticmethod
    def get_translation(language: str, key: str, **kwargs) -> str:
        """Get translated string"""
        translations = LanguageService.TRANSLATIONS.get(
            language, LanguageService.TRANSLATIONS["en"]
        )
        template = translations.get(key, key)
        return template.format(**kwargs) if kwargs else template

    @staticmethod
    def get_supported_languages() -> List[str]:
        return ["en", "sw", "fr"]
