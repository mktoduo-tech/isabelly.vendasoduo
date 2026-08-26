"""Configuração via variáveis de ambiente (GitHub Actions Secrets)."""
import os

# --- Pipedrive ---
PIPEDRIVE_TOKEN = os.environ.get("PIPEDRIVE_TOKEN", "").strip()
PIPEDRIVE_BASE = "https://api.pipedrive.com/v1"

# --- Gemini (Google AI Studio - nível grátis) ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
# Modelo principal + lista de reserva (se um estiver lotado/429/503, tenta o próximo).
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash").strip()
GEMINI_FALLBACK_MODELS = [
    m.strip() for m in os.environ.get(
        "GEMINI_FALLBACK_MODELS", "gemini-flash-latest,gemini-3.6-flash,gemini-3.7-flash"
    ).split(",") if m.strip()
]

# --- Gatilho: só gera briefing para negócios NESTA etapa do funil ---
STAGE_MATCH = os.environ.get("STAGE_MATCH", "agendamento").strip()

# --- Limites ---
# Pega as N ligações MAIS RECENTES (onde costuma estar a qualificação de verdade).
MAX_RECORDINGS = int(os.environ.get("MAX_RECORDINGS", "5"))
MAX_DEALS_SCAN = int(os.environ.get("MAX_DEALS_SCAN", "60"))
MAX_BRIEFINGS_PER_POLL = int(os.environ.get("MAX_BRIEFINGS_PER_POLL", "5"))
