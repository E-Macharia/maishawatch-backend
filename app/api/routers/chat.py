# app/api/routers/chat.py
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Response
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import re
import json
import logging
from app.core.security import current_user, require_roles, optional_user
from app.core.audit import audit
from app.core.db import db
from app.services.data_service import (
    equipment,
    facilities,
    scope_filter,
    telemetry,
    get_equipment_telemetry,
)
from app.ml.predictor import (
    predict_failure_24h,
    predict_failure_72h,
    predict_failure_168h,
    predict_rul,
)
from app.engines.alert_engine import evaluate_equipment
from app.services.chat_service import ChatMemory
from app.ml.risk_config import (
    FAILURE_WARNING_THRESHOLD,
    FAILURE_HIGH_THRESHOLD,
    FAILURE_CRITICAL_THRESHOLD,
)
from app.engines.alert_engine import build_recommendation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["AI Chatbot"])


# --- Models ---
class ChatMessage(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    action: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    suggestions: List[str] = Field(default_factory=list)
    conversation_id: str
    timestamp: str


# --- Intent Detection ---
class IntentDetector:
    """Detect user intent from chat messages"""

    INTENTS = {
        "greeting": [
            "hello",
            "hi",
            "hey",
            "good morning",
            "good afternoon",
            "good evening",
            "habari",
            "bonjour",
            "hallo",
            "konnichiwa",
        ],
        "help": [
            "help",
            "what can you do",
            "how to use",
            "guide",
            "assist",
            "msaada",
            "aide",
            "hilfe",
            "tasukete",
        ],
        "equipment_status": [
            "status",
            "health",
            "condition",
            "operational",
            "working",
            "hali",
            "état",
            "zustand",
            "joutai",
        ],
        "equipment_details": [
            "details",
            "info",
            "information",
            "about",
            "specs",
            "maelezo",
            "détails",
            "informationen",
            "shosai",
        ],
        "failure_prediction": [
            "predict",
            "failure",
            "break",
            "fail",
            "will it fail",
            "probability",
            "utabiri",
            "prédiction",
            "vorhersage",
            "yochi",
        ],
        "rul": [
            "rul",
            "remaining useful life",
            "life span",
            "how long",
            "when will it fail",
            "maisha",
            "durée de vie",
            "lebensdauer",
            "jumyou",
        ],
        "alerts": [
            "alert",
            "alarm",
            "warning",
            "critical",
            "issue",
            "problem",
            "tahadhari",
            "alerte",
            "warnung",
            "keikoku",
        ],
        "maintenance": [
            "maintenance",
            "service",
            "repair",
            "fix",
            "schedule",
            "matengenezo",
            "entretien",
            "wartung",
            "shuuri",
        ],
        "reports": [
            "report",
            "summary",
            "overview",
            "statistics",
            "stats",
            "ripoti",
            "rapport",
            "bericht",
            "houkoku",
        ],
        "recommendations": [
            "recommend",
            "suggest",
            "advice",
            "what should i do",
            "mapendekezo",
            "recommandation",
            "empfehlung",
            "suisen",
        ],
        "facility": [
            "facility",
            "hospital",
            "location",
            "site",
            "kituo",
            "établissement",
            "einrichtung",
            "shisetsu",
        ],
        "analytics": [
            "analytics",
            "trend",
            "pattern",
            "insight",
            "analysis",
            "uchambuzi",
            "analyse",
            "analyse",
            "bunseki",
        ],
        "farewell": [
            "bye",
            "goodbye",
            "see you",
            "thanks",
            "thank you",
            "kwaheri",
            "au revoir",
            "auf wiedersehen",
            "sayonara",
        ],
    }

    EQUIPMENT_KEYWORDS = [
        "mri",
        "ct",
        "ultrasound",
        "ventilator",
        "monitor",
        "x-ray",
        "infusion pump",
        "anesthesia",
        "dialysis",
        "defibrillator",
    ]

    @staticmethod
    def detect_intent(message: str) -> str:
        """Detect the primary intent from the message"""
        message_lower = message.lower()

        for intent, keywords in IntentDetector.INTENTS.items():
            for keyword in keywords:
                if keyword in message_lower:
                    return intent

        for eq_type in IntentDetector.EQUIPMENT_KEYWORDS:
            if eq_type in message_lower:
                return "equipment_details"

        return "general"

    @staticmethod
    def extract_equipment_id(message: str) -> Optional[str]:
        """Extract equipment ID from message if present"""
        pattern = r"EQ-[A-Z0-9-]+"
        match = re.search(pattern, message)
        if match:
            return match.group(0)

        for eq_type in IntentDetector.EQUIPMENT_KEYWORDS:
            if eq_type.lower() in message.lower():
                return eq_type

        return None

    @staticmethod
    def extract_facility_id(message: str) -> Optional[str]:
        """Extract facility ID from message if present"""
        pattern = r"HOSP-[A-Z0-9-]+"
        match = re.search(pattern, message)
        if match:
            return match.group(0)
        return None


# --- Multi-Language Support ---
class LanguageSupport:
    """Multi-language translations for chat responses"""

    TRANSLATIONS = {
        "en": {
            "greeting": "Hello {name}! 👋\n\nI'm your MaishaWatch AI Assistant. You have access to {equipment} equipment across {facilities} facilities.\n\nHere's what I can help you with:\n• 🔍 Check equipment status and details\n• 📊 Get failure predictions and RUL\n• 🚨 View and manage alerts\n• 🔧 Get maintenance recommendations\n• 📈 Generate reports and analytics\n• 💡 Get operational insights\n\nJust ask me anything!",
            "no_equipment": "No equipment found matching your query.",
            "alerts_empty": "✅ No alerts found. All equipment is operating normally!",
            "maintenance_empty": "No maintenance work orders found.",
            "farewell": "👋 Goodbye! Feel free to come back anytime if you need assistance.",
            "help": "📚 **MaishaWatch AI Assistant Help**\n\n**What I can help you with:**\n\n🔍 **Equipment Queries:**\n  • 'Show me all equipment'\n  • 'What's the status of EQ-001?'\n  • 'Tell me about the MRI machine'\n\n📊 **Predictions & Analytics:**\n  • 'Will EQ-001 fail soon?'\n  • 'What's the RUL of the CT scanner?'\n  • 'Show me risk analysis'\n\n🚨 **Alerts:**\n  • 'Show me critical alerts'\n  • 'What alerts are open?'\n  • 'How many alerts today?'\n\n🔧 **Maintenance:**\n  • 'What maintenance is due?'\n  • 'Schedule maintenance for EQ-001'\n  • 'Maintenance recommendations'\n\n📈 **Reports:**\n  • 'Generate facility report'\n  • 'Equipment summary'\n  • 'Maintenance statistics'\n\n💡 **General:**\n  • 'How many facilities?'\n  • 'What's the total equipment?'\n  • 'System health'",
            "suggestions": [
                "What equipment is critical?",
                "Show me alerts",
                "How is equipment performing?",
            ],
            "critical": "CRITICAL",
            "high": "HIGH",
            "medium": "MEDIUM",
            "low": "LOW",
        },
        "sw": {
            "greeting": "Habari {name}! 👋\n\nMimi ni Msaidizi wa AI wa MaishaWatch. Unaweza kufikia vifaa {equipment} katika vituo {facilities}.\n\nHapa ndio ninavyoweza kukusaidia:\n• 🔍 Angalia hali na maelezo ya vifaa\n• 📊 Pata utabiri wa kuharibika na RUL\n• 🚨 Tazama na kudhibiti tahadhari\n• 🔧 Pata mapendekezo ya matengenezo\n• 📈 Tengeneza ripoti na uchambuzi\n• 💡 Pata maarifa ya kiutendaji\n\nUliza chochote!",
            "no_equipment": "Hakuna kifaa kilichopatikana kinacholingana na swali lako.",
            "alerts_empty": "✅ Hakuna tahadhari zilizopatikana. Vifaa vyote vinafanya kazi kawaida!",
            "maintenance_empty": "Hakuna maagizo ya matengenezo yaliyopatikana.",
            "farewell": "👋 Kwaheri! Karibu tena wakati wowote unapohitaji msaada.",
            "help": "📚 **Msaada wa Msaidizi wa AI wa MaishaWatch**\n\n**Ninavyoweza kukusaidia:**\n\n🔍 **Maswali ya Vifaa:**\n  • 'Nionyeshe vifaa vyote'\n  • 'Hali ya EQ-001 ikoje?'\n  • 'Niambie kuhusu mashine ya MRI'\n\n📊 **Utabiri na Uchambuzi:**\n  • 'Je, EQ-001 itaharibika hivi karibuni?'\n  • 'RUL ya CT scanner ni nini?'\n  • 'Nionyeshe uchambuzi wa hatari'\n\n🚨 **Tahadhari:**\n  • 'Nionyeshe tahadhari muhimu'\n  • 'Tahadhari zipi ziko wazi?'\n  • 'Tahadhari ngapi leo?'\n\n🔧 **Matengenezo:**\n  • 'Ni matengenezo gani yanayotarajiwa?'\n  • 'Ratiba matengenezo ya EQ-001'\n  • 'Mapendekezo ya matengenezo'\n\n📈 **Ripoti:**\n  • 'Tengeneza ripoti ya kituo'\n  • 'Muhtasari wa vifaa'\n  • 'Takwimu za matengenezo'",
            "suggestions": [
                "Vifaa gani ni muhimu?",
                "Nionyeshe tahadhari",
                "Vifaa vinafanya kazi vipi?",
            ],
            "critical": "MUHIMU SANA",
            "high": "JUU",
            "medium": "WASTANI",
            "low": "CHINI",
        },
        "fr": {
            "greeting": "Bonjour {name}! 👋\n\nJe suis votre Assistant IA MaishaWatch. Vous avez accès à {equipment} équipements dans {facilities} établissements.\n\nVoici ce que je peux faire pour vous :\n• 🔍 Vérifier l'état et les détails des équipements\n• 📊 Obtenir des prédictions de panne et RUL\n• 🚨 Voir et gérer les alertes\n• 🔧 Obtenir des recommandations de maintenance\n• 📈 Générer des rapports et analyses\n• 💡 Obtenir des informations opérationnelles\n\nDemandez-moi n'importe quoi !",
            "no_equipment": "Aucun équipement trouvé correspondant à votre recherche.",
            "alerts_empty": "✅ Aucune alerte trouvée. Tous les équipements fonctionnent normalement !",
            "maintenance_empty": "Aucun ordre de maintenance trouvé.",
            "farewell": "👋 Au revoir ! N'hésitez pas à revenir quand vous aurez besoin d'aide.",
            "help": "📚 **Aide de l'Assistant IA MaishaWatch**\n\n**Ce que je peux faire :**\n\n🔍 **Requêtes sur les Équipements :**\n  • 'Montrez-moi tous les équipements'\n  • 'Quel est l'état de EQ-001 ?'\n  • 'Parlez-moi de l'IRM'\n\n📊 **Prédictions et Analyses :**\n  • 'EQ-001 va-t-il tomber en panne ?'\n  • 'Quelle est la RUL du scanner CT ?'\n  • 'Montrez-moi l'analyse des risques'\n\n🚨 **Alertes :**\n  • 'Montrez-moi les alertes critiques'\n  • 'Quelles alertes sont ouvertes ?'\n  • 'Combien d'alertes aujourd'hui ?'\n\n🔧 **Maintenance :**\n  • 'Quelle maintenance est due ?'\n  • 'Planifier la maintenance de EQ-001'\n  • 'Recommandations de maintenance'",
            "suggestions": [
                "Quels équipements sont critiques?",
                "Montrez-moi les alertes",
                "Comment fonctionne l'équipement?",
            ],
            "critical": "CRITIQUE",
            "high": "ÉLEVÉ",
            "medium": "MOYEN",
            "low": "FAIBLE",
        },
        "de": {
            "greeting": "Hallo {name}! 👋\n\nIch bin Ihr MaishaWatch KI-Assistent. Sie haben Zugriff auf {equipment} Geräte in {facilities} Einrichtungen.\n\nHier ist, womit ich helfen kann:\n• 🔍 Gerätestatus und Details prüfen\n• 📊 Ausfallvorhersagen und RUL erhalten\n• 🚨 Warnungen anzeigen und verwalten\n• 🔧 Wartungsempfehlungen erhalten\n• 📈 Berichte und Analysen erstellen\n• 💡 Betriebliche Einblicke erhalten\n\nFragen Sie mich einfach alles!",
            "no_equipment": "Keine Geräte gefunden, die Ihrer Anfrage entsprechen.",
            "alerts_empty": "✅ Keine Warnungen gefunden. Alle Geräte arbeiten normal!",
            "maintenance_empty": "Keine Wartungsaufträge gefunden.",
            "farewell": "👋 Auf Wiedersehen! Kommen Sie jederzeit gerne wieder, wenn Sie Hilfe benötigen.",
            "help": "📚 **MaishaWatch KI-Assistent Hilfe**\n\n**Womit ich helfen kann:**\n\n🔍 **Geräteanfragen:**\n  • 'Zeige mir alle Geräte'\n  • 'Wie ist der Status von EQ-001?'\n  • 'Erzähle mir vom MRT-Gerät'\n\n📊 **Vorhersagen und Analysen:**\n  • 'Wird EQ-001 bald ausfallen?'\n  • 'Wie hoch ist die RUL des CT-Scanners?'\n  • 'Zeige mir die Risikoanalyse'\n\n🚨 **Warnungen:**\n  • 'Zeige mir kritische Warnungen'\n  • 'Welche Warnungen sind offen?'\n  • 'Wie viele Warnungen heute?'\n\n🔧 **Wartung:**\n  • 'Welche Wartung steht an?'\n  • 'Wartung für EQ-001 planen'\n  • 'Wartungsempfehlungen'",
            "suggestions": [
                "Welche Geräte sind kritisch?",
                "Zeige mir Warnungen",
                "Wie funktionieren die Geräte?",
            ],
            "critical": "KRITISCH",
            "high": "HOCH",
            "medium": "MITTEL",
            "low": "NIEDRIG",
        },
        "ja": {
            "greeting": "こんにちは {name}さん！👋\n\n私はMaishaWatch AIアシスタントです。{equipment}台の機器と{facilities}施設にアクセスできます。\n\n以下のことができます：\n• 🔍 機器の状態と詳細を確認\n• 📊 故障予測とRULを取得\n• 🚨 アラートの表示と管理\n• 🔧 メンテナンスの推奨事項を取得\n• 📈 レポートと分析を生成\n• 💡 運用に関する洞察を得る\n\n何でも聞いてください！",
            "no_equipment": "お探しの機器が見つかりませんでした。",
            "alerts_empty": "✅ アラートは見つかりませんでした。すべての機器は正常に動作しています！",
            "maintenance_empty": "メンテナンス作業指示書は見つかりませんでした。",
            "farewell": "👋 さようなら！いつでもお気軽に戻ってきてください。",
            "help": "📚 **MaishaWatch AIアシスタント ヘルプ**\n\n**できること：**\n\n🔍 **機器に関する質問：**\n  • 'すべての機器を表示'\n  • 'EQ-001のステータスは？'\n  • 'MRI装置について教えて'\n\n📊 **予測と分析：**\n  • 'EQ-001はすぐに故障しますか？'\n  • 'CTスキャナーのRULは？'\n  • 'リスク分析を表示'\n\n🚨 **アラート：**\n  • '重要なアラートを表示'\n  • 'どのアラートが開いていますか？'\n  • '今日のアラート数は？'\n\n🔧 **メンテナンス：**\n  • 'メンテナンス予定は？'\n  • 'EQ-001のメンテナンスを計画'\n  • 'メンテナンスの推奨事項'",
            "suggestions": [
                "どの機器が重要ですか？",
                "アラートを表示",
                "機器のパフォーマンスはどうですか？",
            ],
            "critical": "致命的",
            "high": "高",
            "medium": "中",
            "low": "低",
        },
    }

    @staticmethod
    def get_translation(language: str, key: str, **kwargs) -> str:
        """Get translated text for the specified language"""
        translations = LanguageSupport.TRANSLATIONS.get(
            language, LanguageSupport.TRANSLATIONS["en"]
        )
        template = translations.get(
            key, LanguageSupport.TRANSLATIONS["en"].get(key, key)
        )

        # Replace placeholders
        for key, value in kwargs.items():
            template = template.replace(f"{{{key}}}", str(value))

        return template

    @staticmethod
    def get_suggestions(language: str) -> List[str]:
        """Get translated suggestions"""
        translations = LanguageSupport.TRANSLATIONS.get(
            language, LanguageSupport.TRANSLATIONS["en"]
        )
        return translations.get(
            "suggestions", LanguageSupport.TRANSLATIONS["en"]["suggestions"]
        )


# --- Chat Service ---
class ChatService:
    """Main chat service handling all queries with multi-language support"""

    def __init__(self, user, language: str = "en"):
        self.user = user
        self.language = language
        self.scope = user.get("scope_type", "national")
        self.scope_id = user.get("scope_id")
        self.equipment_list = scope_filter(equipment(), user)
        self.facilities_list = scope_filter(facilities(), user)

    def process_query(self, message: str) -> ChatResponse:
        """Process user query and generate response with language support"""
        intent = IntentDetector.detect_intent(message)
        equipment_id = IntentDetector.extract_equipment_id(message)
        facility_id = IntentDetector.extract_facility_id(message)

        if intent == "greeting":
            return self._handle_greeting()
        elif intent == "help":
            return self._handle_help()
        elif intent == "equipment_status":
            return self._handle_equipment_status(equipment_id, facility_id)
        elif intent == "equipment_details":
            return self._handle_equipment_details(equipment_id, facility_id)
        elif intent == "failure_prediction":
            return self._handle_failure_prediction(equipment_id, facility_id)
        elif intent == "rul":
            return self._handle_rul(equipment_id, facility_id)
        elif intent == "alerts":
            return self._handle_alerts(equipment_id, facility_id)
        elif intent == "maintenance":
            return self._handle_maintenance(equipment_id, facility_id)
        elif intent == "reports":
            return self._handle_reports(facility_id)
        elif intent == "recommendations":
            return self._handle_recommendations(equipment_id, facility_id)
        elif intent == "facility":
            return self._handle_facility_info(facility_id)
        elif intent == "analytics":
            return self._handle_analytics(facility_id)
        elif intent == "farewell":
            return self._handle_farewell()
        else:
            return self._handle_general(message)

    def _handle_greeting(self) -> ChatResponse:
        """Handle greeting messages with language support"""
        name = self.user.get("name", "User")
        response = LanguageSupport.get_translation(
            self.language,
            "greeting",
            name=name,
            equipment=len(self.equipment_list),
            facilities=len(self.facilities_list),
        )

        suggestions = LanguageSupport.get_suggestions(self.language)

        return ChatResponse(
            response=response,
            action="greeting",
            data={
                "equipment_count": len(self.equipment_list),
                "facility_count": len(self.facilities_list),
            },
            suggestions=suggestions,
            conversation_id=f"chat_{datetime.now(timezone.utc).timestamp()}",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def _handle_help(self) -> ChatResponse:
        """Handle help requests with language support"""
        response = LanguageSupport.get_translation(self.language, "help")
        suggestions = LanguageSupport.get_suggestions(self.language)

        return ChatResponse(
            response=response,
            action="help",
            data=None,
            suggestions=suggestions,
            conversation_id=f"chat_{datetime.now(timezone.utc).timestamp()}",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def _handle_equipment_status(
        self, equipment_id: Optional[str], facility_id: Optional[str]
    ) -> ChatResponse:
        """Handle equipment status queries"""
        eq_list = self.equipment_list
        if equipment_id:
            eq_list = [e for e in eq_list if str(e.get("equipment_id")) == equipment_id]
        elif facility_id:
            eq_list = [e for e in eq_list if str(e.get("facility_id")) == facility_id]

        if not eq_list:
            response = LanguageSupport.get_translation(self.language, "no_equipment")
            return ChatResponse(
                response=response,
                action="error",
                data=None,
                suggestions=LanguageSupport.get_suggestions(self.language),
                conversation_id=f"chat_{datetime.now(timezone.utc).timestamp()}",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        if len(eq_list) == 1:
            eq = eq_list[0]
            status_icons = {
                "OPERATIONAL": "✅",
                "MAINTENANCE": "🔧",
                "DECOMMISSIONED": "❌",
            }
            status_icon = status_icons.get(eq.get("status", "UNKNOWN"), "❓")

            telemetry_data = get_equipment_telemetry(eq.get("equipment_id"), limit=1)
            latest = telemetry_data[0] if telemetry_data else None

            response = f"📊 **Equipment Status: {eq.get('equipment_id')}**\n\n"
            response += f"**Type:** {eq.get('equipment_type', 'Unknown')}\n"
            response += f"**Status:** {status_icon} {eq.get('status', 'UNKNOWN')}\n"
            response += f"**Manufacturer:** {eq.get('manufacturer', 'N/A')}\n"
            response += f"**Model:** {eq.get('model', 'N/A')}\n"
            response += f"**Facility:** {eq.get('facility_id', 'N/A')}\n\n"

            if latest:
                response += "📡 **Latest Telemetry:**\n"
                response += f"  • Temperature: {latest.get('temperature', 'N/A')}°C\n"
                response += (
                    f"  • Risk Score: {latest.get('risk_score', 0) * 100:.1f}%\n"
                )
                response += (
                    f"  • Status: {latest.get('operational_status', 'NORMAL')}\n"
                )

            return ChatResponse(
                response=response,
                action="equipment_status",
                data={"equipment": eq, "telemetry": latest},
                suggestions=LanguageSupport.get_suggestions(self.language),
                conversation_id=f"chat_{datetime.now(timezone.utc).timestamp()}",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        else:
            response = f"📋 **Found {len(eq_list)} equipment**\n\n"
            for eq in eq_list[:10]:
                status_icon = "✅" if eq.get("status") == "OPERATIONAL" else "🔧"
                response += f"• {eq.get('equipment_id')}: {eq.get('equipment_type')} {status_icon}\n"
            if len(eq_list) > 10:
                response += f"\n... and {len(eq_list) - 10} more equipment"

            return ChatResponse(
                response=response,
                action="equipment_list",
                data={"equipment": eq_list[:10], "total": len(eq_list)},
                suggestions=LanguageSupport.get_suggestions(self.language),
                conversation_id=f"chat_{datetime.now(timezone.utc).timestamp()}",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

    def _handle_equipment_details(
        self, equipment_id: Optional[str], facility_id: Optional[str]
    ) -> ChatResponse:
        """Handle equipment details queries"""
        return self._handle_equipment_status(equipment_id, facility_id)

    def _handle_failure_prediction(
        self, equipment_id: Optional[str], facility_id: Optional[str]
    ) -> ChatResponse:
        """Handle failure prediction queries"""
        if not equipment_id:
            eq_list = self.equipment_list
            if facility_id:
                eq_list = [
                    e for e in eq_list if str(e.get("facility_id")) == facility_id
                ]
            if not eq_list:
                response = LanguageSupport.get_translation(
                    self.language, "no_equipment"
                )
                return ChatResponse(
                    response=response,
                    action="error",
                    data=None,
                    suggestions=LanguageSupport.get_suggestions(self.language),
                    conversation_id=f"chat_{datetime.now(timezone.utc).timestamp()}",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
            equipment_id = eq_list[0].get("equipment_id")

        try:
            p24, _ = predict_failure_24h(equipment_id)
            p72, _ = predict_failure_72h(equipment_id)
            p168, _ = predict_failure_168h(equipment_id)
            rul, _ = predict_rul(equipment_id)
            eq = next(
                (
                    e
                    for e in self.equipment_list
                    if str(e.get("equipment_id")) == equipment_id
                ),
                {},
            )

            max_prob = max(p24, p72, p168)
            severity = "LOW"
            severity_label = LanguageSupport.get_translation(self.language, "low")
            if max_prob >= FAILURE_CRITICAL_THRESHOLD:
                severity = "CRITICAL"
                severity_label = LanguageSupport.get_translation(
                    self.language, "critical"
                )
            elif max_prob >= FAILURE_HIGH_THRESHOLD:
                severity = "HIGH"
                severity_label = LanguageSupport.get_translation(self.language, "high")
            elif max_prob >= FAILURE_WARNING_THRESHOLD:
                severity = "MEDIUM"
                severity_label = LanguageSupport.get_translation(
                    self.language, "medium"
                )

            severity_icons = {
                "CRITICAL": "🚨",
                "HIGH": "🔴",
                "MEDIUM": "🟡",
                "LOW": "🟢",
            }

            response = f"🔮 **Failure Prediction for {equipment_id}**\n\n"
            response += f"**Equipment:** {eq.get('equipment_type', 'Unknown')}\n"
            response += f"**Severity:** {severity_icons.get(severity, 'ℹ️')} {severity_label}\n\n"
            response += f"**Failure Probability:**\n"
            response += f"  • 24 hours: {p24 * 100:.1f}%\n"
            response += f"  • 72 hours: {p72 * 100:.1f}%\n"
            response += f"  • 168 hours: {p168 * 100:.1f}%\n\n"
            response += (
                f"**Remaining Useful Life:** {rul:.1f} hours ({rul/24:.1f} days)\n\n"
            )

            if severity == "CRITICAL":
                response += "⚠️ **CRITICAL: Immediate action required!**"
            elif severity == "HIGH":
                response += "🔴 **HIGH: Urgent maintenance required**"
            elif severity == "MEDIUM":
                response += "🟡 **MEDIUM: Schedule maintenance**"
            else:
                response += "🟢 **LOW: Normal operation**"

            return ChatResponse(
                response=response,
                action="failure_prediction",
                data={
                    "equipment_id": equipment_id,
                    "p24": p24,
                    "p72": p72,
                    "p168": p168,
                    "rul": rul,
                    "severity": severity,
                },
                suggestions=LanguageSupport.get_suggestions(self.language),
                conversation_id=f"chat_{datetime.now(timezone.utc).timestamp()}",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        except Exception as e:
            logger.error(f"Error getting predictions: {e}")
            response = f"Unable to get predictions for {equipment_id}. Please ensure the equipment has telemetry data."
            return ChatResponse(
                response=response,
                action="error",
                data=None,
                suggestions=LanguageSupport.get_suggestions(self.language),
                conversation_id=f"chat_{datetime.now(timezone.utc).timestamp()}",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

    def _handle_rul(
        self, equipment_id: Optional[str], facility_id: Optional[str]
    ) -> ChatResponse:
        """Handle RUL queries"""
        if not equipment_id:
            eq_list = self.equipment_list
            if facility_id:
                eq_list = [
                    e for e in eq_list if str(e.get("facility_id")) == facility_id
                ]
            if eq_list:
                equipment_id = eq_list[0].get("equipment_id")
            else:
                return ChatResponse(
                    response="Please specify an equipment ID to check RUL.",
                    action="error",
                    data=None,
                    suggestions=LanguageSupport.get_suggestions(self.language),
                    conversation_id=f"chat_{datetime.now(timezone.utc).timestamp()}",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )

        try:
            rul, equipment_type = predict_rul(equipment_id)
            eq = next(
                (
                    e
                    for e in self.equipment_list
                    if str(e.get("equipment_id")) == equipment_id
                ),
                {},
            )

            response = f"⏳ **Remaining Useful Life for {equipment_id}**\n\n"
            response += f"**Equipment:** {eq.get('equipment_type', equipment_type)}\n"
            response += f"**RUL:** {rul:.1f} hours ({rul/24:.1f} days)\n\n"

            if rul < 24:
                response += "⚠️ **Critical: Less than 24 hours remaining!**"
            elif rul < 72:
                response += "🔴 **High: Less than 3 days remaining**"
            elif rul < 168:
                response += "🟡 **Medium: Less than 7 days remaining**"
            else:
                response += "🟢 **Normal: More than 7 days remaining**"

            return ChatResponse(
                response=response,
                action="rul",
                data={
                    "equipment_id": equipment_id,
                    "rul_hours": rul,
                    "rul_days": rul / 24,
                },
                suggestions=LanguageSupport.get_suggestions(self.language),
                conversation_id=f"chat_{datetime.now(timezone.utc).timestamp()}",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        except Exception as e:
            logger.error(f"Error getting RUL: {e}")
            return ChatResponse(
                response=f"Unable to calculate RUL for {equipment_id}.",
                action="error",
                data=None,
                suggestions=LanguageSupport.get_suggestions(self.language),
                conversation_id=f"chat_{datetime.now(timezone.utc).timestamp()}",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

    def _handle_alerts(
        self, equipment_id: Optional[str], facility_id: Optional[str]
    ) -> ChatResponse:
        """Handle alert queries"""
        with db() as c:
            query = "SELECT * FROM alerts WHERE 1=1"
            params = []
            if equipment_id:
                query += " AND equipment_id=?"
                params.append(equipment_id)
            if facility_id:
                query += " AND facility_id=?"
                params.append(facility_id)
            query += " ORDER BY created_at DESC LIMIT 20"
            alerts_data = [dict(r) for r in c.execute(query, params).fetchall()]

        alerts_data = scope_filter(alerts_data, self.user)

        if not alerts_data:
            response = LanguageSupport.get_translation(self.language, "alerts_empty")
            return ChatResponse(
                response=response,
                action="alerts_empty",
                data=None,
                suggestions=LanguageSupport.get_suggestions(self.language),
                conversation_id=f"chat_{datetime.now(timezone.utc).timestamp()}",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        severity_counts = {}
        for alert in alerts_data:
            severity = alert.get("severity", "UNKNOWN")
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

        response = f"🚨 **Alerts Summary**\n\n"
        response += f"**Total Alerts:** {len(alerts_data)}\n\n"
        response += "**By Severity:**\n"
        for severity, count in severity_counts.items():
            icon = (
                "🚨"
                if severity == "CRITICAL"
                else (
                    "🔴"
                    if severity == "HIGH"
                    else "🟡" if severity == "MEDIUM" else "🟢"
                )
            )
            severity_label = LanguageSupport.get_translation(
                self.language, severity.lower()
            )
            response += f"  • {icon} {severity_label}: {count}\n"

        return ChatResponse(
            response=response,
            action="alerts_summary",
            data={"alerts": alerts_data, "severity_counts": severity_counts},
            suggestions=LanguageSupport.get_suggestions(self.language),
            conversation_id=f"chat_{datetime.now(timezone.utc).timestamp()}",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def _handle_maintenance(
        self, equipment_id: Optional[str], facility_id: Optional[str]
    ) -> ChatResponse:
        """Handle maintenance queries"""
        with db() as c:
            query = "SELECT * FROM maintenance_work_orders WHERE 1=1"
            params = []
            if equipment_id:
                query += " AND equipment_id=?"
                params.append(equipment_id)
            if facility_id:
                query += " AND facility_id=?"
                params.append(facility_id)
            query += " ORDER BY created_at DESC LIMIT 20"
            work_orders = [dict(r) for r in c.execute(query, params).fetchall()]

        if self.scope != "national":
            work_orders = [
                w for w in work_orders if str(w.get("facility_id")) == self.scope_id
            ]

        if not work_orders:
            response = LanguageSupport.get_translation(
                self.language, "maintenance_empty"
            )
            return ChatResponse(
                response=response,
                action="maintenance_empty",
                data=None,
                suggestions=LanguageSupport.get_suggestions(self.language),
                conversation_id=f"chat_{datetime.now(timezone.utc).timestamp()}",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        status_counts = {}
        for wo in work_orders:
            status = wo.get("status", "UNKNOWN")
            status_counts[status] = status_counts.get(status, 0) + 1

        response = f"🔧 **Maintenance Work Orders**\n\n"
        response += f"**Total Work Orders:** {len(work_orders)}\n"
        response += "**Status Breakdown:**\n"
        for status, count in status_counts.items():
            icon = "🟡" if status == "OPEN" else "✅" if status == "RESOLVED" else "🔧"
            response += f"  • {icon} {status}: {count}\n"

        return ChatResponse(
            response=response,
            action="maintenance_summary",
            data={"work_orders": work_orders, "status_counts": status_counts},
            suggestions=LanguageSupport.get_suggestions(self.language),
            conversation_id=f"chat_{datetime.now(timezone.utc).timestamp()}",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def _handle_reports(self, facility_id: Optional[str]) -> ChatResponse:
        """Handle report queries"""
        facility_name = "all facilities"
        if facility_id:
            facility = next(
                (
                    f
                    for f in self.facilities_list
                    if str(f.get("facility_id")) == facility_id
                ),
                None,
            )
            if facility:
                facility_name = facility.get("facility_name", facility_id)

        eq = self.equipment_list
        if facility_id:
            eq = [e for e in eq if str(e.get("facility_id")) == facility_id]

        total = len(eq)
        operational = len([e for e in eq if e.get("status") == "OPERATIONAL"])
        maintenance = len([e for e in eq if e.get("status") == "MAINTENANCE"])

        response = f"📈 **Report for {facility_name}**\n\n"
        response += f"**Equipment Summary:**\n"
        response += f"  • Total Equipment: {total}\n"
        response += f"  • Operational: {operational}\n"
        response += f"  • Maintenance: {maintenance}\n"

        return ChatResponse(
            response=response,
            action="report",
            data={
                "facility_id": facility_id,
                "statistics": {
                    "total": total,
                    "operational": operational,
                    "maintenance": maintenance,
                },
            },
            suggestions=LanguageSupport.get_suggestions(self.language),
            conversation_id=f"chat_{datetime.now(timezone.utc).timestamp()}",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def _handle_recommendations(
        self, equipment_id: Optional[str], facility_id: Optional[str]
    ) -> ChatResponse:
        """Handle recommendation queries"""
        if equipment_id:
            eq = next(
                (
                    e
                    for e in self.equipment_list
                    if str(e.get("equipment_id")) == equipment_id
                ),
                None,
            )
            if not eq:
                response = f"Equipment {equipment_id} not found."
                return ChatResponse(
                    response=response,
                    action="error",
                    data=None,
                    suggestions=LanguageSupport.get_suggestions(self.language),
                    conversation_id=f"chat_{datetime.now(timezone.utc).timestamp()}",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )

            try:
                p24, _ = predict_failure_24h(equipment_id)
                p72, _ = predict_failure_72h(equipment_id)
                p168, _ = predict_failure_168h(equipment_id)
                rul, _ = predict_rul(equipment_id)
                max_prob = max(p24, p72, p168)

                severity = "LOW"
                if max_prob >= FAILURE_CRITICAL_THRESHOLD:
                    severity = "CRITICAL"
                elif max_prob >= FAILURE_HIGH_THRESHOLD:
                    severity = "HIGH"
                elif max_prob >= FAILURE_WARNING_THRESHOLD:
                    severity = "MEDIUM"

                recommendation = build_recommendation(severity, max_prob, rul)
                severity_label = LanguageSupport.get_translation(
                    self.language, severity.lower()
                )

                response = f"💡 **Recommendations for {equipment_id}**\n\n"
                response += f"**Equipment:** {eq.get('equipment_type', 'Unknown')}\n"
                response += f"**Risk Level:** {severity_label}\n\n"
                response += f"**Action Required:**\n{recommendation}\n\n"

                if severity == "CRITICAL":
                    response += "⚠️ **Immediate Action Required!**"
                elif severity == "HIGH":
                    response += "🔴 **Urgent Action Required**"
                else:
                    response += "🟢 **Continue Monitoring**"

            except Exception as e:
                response = f"Unable to generate recommendations for {equipment_id}."
        else:
            response = "💡 **General Recommendations**\n\n"
            response += "• Review critical alerts daily\n"
            response += "• Monitor high-risk equipment\n"
            response += "• Schedule preventive maintenance\n"
            response += "• Update equipment inventory\n\n"
            response += (
                "For specific recommendations, ask: 'Recommendations for EQ-001'"
            )

        return ChatResponse(
            response=response,
            action="recommendations",
            data={"equipment_id": equipment_id},
            suggestions=LanguageSupport.get_suggestions(self.language),
            conversation_id=f"chat_{datetime.now(timezone.utc).timestamp()}",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def _handle_facility_info(self, facility_id: Optional[str]) -> ChatResponse:
        """Handle facility queries"""
        if not facility_id and self.facilities_list:
            facility_id = self.facilities_list[0].get("facility_id")

        if facility_id:
            facility = next(
                (
                    f
                    for f in self.facilities_list
                    if str(f.get("facility_id")) == facility_id
                ),
                None,
            )
            if not facility:
                response = f"Facility {facility_id} not found."
                return ChatResponse(
                    response=response,
                    action="error",
                    data=None,
                    suggestions=LanguageSupport.get_suggestions(self.language),
                    conversation_id=f"chat_{datetime.now(timezone.utc).timestamp()}",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )

            eq_count = len(
                [
                    e
                    for e in self.equipment_list
                    if str(e.get("facility_id")) == facility_id
                ]
            )

            response = f"🏥 **Facility Information**\n\n"
            response += f"**ID:** {facility.get('facility_id')}\n"
            response += f"**Name:** {facility.get('facility_name', 'N/A')}\n"
            response += f"**County:** {facility.get('county', 'N/A')}\n"
            response += f"**Equipment Count:** {eq_count}\n"
        else:
            response = f"🏥 **Available Facilities ({len(self.facilities_list)})**\n\n"
            for f in self.facilities_list[:10]:
                eq_count = len(
                    [
                        e
                        for e in self.equipment_list
                        if str(e.get("facility_id")) == str(f.get("facility_id"))
                    ]
                )
                response += f"• {f.get('facility_id')}: {f.get('facility_name', 'N/A')} ({eq_count} equipment)\n"

        return ChatResponse(
            response=response,
            action="facility_info",
            data={"facility": facility if facility_id else None},
            suggestions=LanguageSupport.get_suggestions(self.language),
            conversation_id=f"chat_{datetime.now(timezone.utc).timestamp()}",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def _handle_analytics(self, facility_id: Optional[str]) -> ChatResponse:
        """Handle analytics queries"""
        eq = self.equipment_list
        if facility_id:
            eq = [e for e in eq if str(e.get("facility_id")) == facility_id]

        type_counts = {}
        for e in eq:
            eq_type = e.get("equipment_type", "Unknown")
            type_counts[eq_type] = type_counts.get(eq_type, 0) + 1

        status_counts = {}
        for e in eq:
            status = e.get("status", "Unknown")
            status_counts[status] = status_counts.get(status, 0) + 1

        response = f"📊 **Analytics Dashboard**\n\n"
        response += f"**Total Equipment:** {len(eq)}\n\n"
        response += "**Equipment by Type:**\n"
        for eq_type, count in sorted(
            type_counts.items(), key=lambda x: x[1], reverse=True
        )[:5]:
            response += f"  • {eq_type}: {count}\n"

        return ChatResponse(
            response=response,
            action="analytics",
            data={"type_counts": type_counts, "status_counts": status_counts},
            suggestions=LanguageSupport.get_suggestions(self.language),
            conversation_id=f"chat_{datetime.now(timezone.utc).timestamp()}",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def _handle_farewell(self) -> ChatResponse:
        """Handle farewell messages"""
        response = LanguageSupport.get_translation(self.language, "farewell")
        return ChatResponse(
            response=response,
            action="farewell",
            data=None,
            suggestions=LanguageSupport.get_suggestions(self.language),
            conversation_id=f"chat_{datetime.now(timezone.utc).timestamp()}",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def _handle_general(self, message: str) -> ChatResponse:
        """Handle general queries"""
        message_lower = message.lower()

        if "how many" in message_lower or "count" in message_lower:
            if "equipment" in message_lower:
                response = (
                    f"You have {len(self.equipment_list)} equipment in your scope."
                )
                return ChatResponse(
                    response=response,
                    action="general",
                    data={"count": len(self.equipment_list), "type": "equipment"},
                    suggestions=LanguageSupport.get_suggestions(self.language),
                    conversation_id=f"chat_{datetime.now(timezone.utc).timestamp()}",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
            elif "facility" in message_lower:
                response = f"You have access to {len(self.facilities_list)} facilities."
                return ChatResponse(
                    response=response,
                    action="general",
                    data={"count": len(self.facilities_list), "type": "facilities"},
                    suggestions=LanguageSupport.get_suggestions(self.language),
                    conversation_id=f"chat_{datetime.now(timezone.utc).timestamp()}",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )

        response = "I can help with equipment status, predictions, alerts, maintenance, and reports. Could you rephrase your question?"
        return ChatResponse(
            response=response,
            action="general",
            data=None,
            suggestions=LanguageSupport.get_suggestions(self.language),
            conversation_id=f"chat_{datetime.now(timezone.utc).timestamp()}",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )


# --- API Endpoints ---


@router.post("", response_model=ChatResponse)
def chat(message: ChatMessage, u=Depends(optional_user)):
    """Send a message to the AI chatbot with multi-language support"""
    try:
        # Extract language from context
        language = message.context.get("language", "en") if message.context else "en"
        conversation_id = message.conversation_id

        # Create new conversation if not exists
        if not conversation_id:
            conversations = ChatMemory.get_conversations(u["id"], limit=1)
            if conversations:
                conversation_id = conversations[0]["conversation_id"]
            else:
                conversation_id = ChatMemory.create_conversation(u["id"])

        # Save user message
        ChatMemory.add_message(conversation_id, "user", message.message)

        # Process the query with language
        chat_service = ChatService(u, language)
        response = chat_service.process_query(message.message)

        # Save assistant response
        ChatMemory.add_message(
            conversation_id,
            "assistant",
            response.response,
            response.action,
            response.data,
        )

        # Return response with conversation_id
        response.conversation_id = conversation_id

        # Log the query
        audit(
            u,
            "CHAT_QUERY",
            "chat",
            details={
                "message": message.message,
                "conversation_id": conversation_id,
                "action": response.action,
                "language": language,
            },
        )

        return response

    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(500, f"Chat service error: {str(e)}")


@router.get("/conversations")
def get_conversations(limit: int = 20, u=Depends(optional_user)):
    """Get user's conversation history"""
    conversations = ChatMemory.get_conversations(u["id"], limit)
    return {"conversations": conversations, "total": len(conversations)}


@router.get("/conversations/{conversation_id}")
def get_conversation_history(
    conversation_id: str, limit: int = 50, u=Depends(optional_user)
):
    """Get full conversation history"""
    conversations = ChatMemory.get_conversations(u["id"], limit=100)
    if not any(c["conversation_id"] == conversation_id for c in conversations):
        raise HTTPException(403, "You don't have access to this conversation")

    messages = ChatMemory.get_conversation(conversation_id, limit)
    return {
        "conversation_id": conversation_id,
        "messages": messages,
        "total": len(messages),
    }


@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str, u=Depends(optional_user)):
    """Delete a conversation"""
    conversations = ChatMemory.get_conversations(u["id"], limit=100)
    if not any(c["conversation_id"] == conversation_id for c in conversations):
        raise HTTPException(403, "You don't have access to this conversation")

    ChatMemory.delete_conversation(conversation_id)
    return {"message": "Conversation deleted successfully"}


@router.get("/suggestions")
def get_suggestions(u=Depends(optional_user)):
    """Get suggested questions based on user context"""
    eq_count = len(scope_filter(equipment(), u))

    with db() as c:
        alert_count = c.execute(
            "SELECT COUNT(*) as count FROM alerts WHERE status='OPEN'"
        ).fetchone()

    suggestions = [
        "What's the status of all equipment?",
        "Show me critical alerts",
        "Predict failures for equipment",
        "What maintenance is due?",
        "Generate facility report",
        "Recommendations for equipment",
        "How many equipment do I have?",
        "What are the latest alerts?",
        "Analytics dashboard",
        "Help me with maintenance",
    ]

    if alert_count and alert_count["count"] > 0:
        suggestions.insert(0, f"Show me {alert_count['count']} open alerts")

    return {
        "suggestions": suggestions[:10],
        "equipment_count": eq_count,
        "alert_count": alert_count["count"] if alert_count else 0,
    }


@router.get("/conversations/{conversation_id}/export")
def export_conversation(
    conversation_id: str, format: str = "json", u=Depends(optional_user)
):
    """Export a conversation in specified format"""
    # Verify ownership
    conversations = ChatMemory.get_conversations(u["id"], limit=100)
    if not any(c["conversation_id"] == conversation_id for c in conversations):
        raise HTTPException(403, "You don't have access to this conversation")

    # Get messages
    messages = ChatMemory.get_conversation(conversation_id, limit=1000)

    # Export based on format
    if format == "json":
        content = json.dumps(
            {
                "conversation_id": conversation_id,
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "messages": messages,
            },
            indent=2,
        )
        media_type = "application/json"
        filename = f"conversation_{conversation_id}.json"
    elif format == "csv":
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Role", "Content", "Action", "Created At"])
        for msg in messages:
            writer.writerow(
                [
                    msg.get("role", ""),
                    msg.get("content", ""),
                    msg.get("action", ""),
                    msg.get("created_at", ""),
                ]
            )
        content = output.getvalue()
        media_type = "text/csv"
        filename = f"conversation_{conversation_id}.csv"
    else:
        raise HTTPException(400, f"Unsupported format: {format}")

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
