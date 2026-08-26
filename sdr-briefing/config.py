"""Configuração via variáveis de ambiente (GitHub Actions Secrets)."""
import os

# --- Pipedrive ---
PIPEDRIVE_TOKEN = os.environ.get("PIPEDRIVE_TOKEN", "").strip()
PIPEDRIVE_BASE = "https://api.pipedrive.com/v1"

# --- Gemini (Google AI Studio - nível grátis) ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash").strip()
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"

# --- Gatilho: só gera briefing para negócios NESTA etapa do funil ---
# (ou seja, quando o SDR passa o card para "Agendamento" = reunião marcada).
# Casa qualquer etapa cujo nome CONTENHA este texto (sem diferenciar maiúsc./minúsc.).
STAGE_MATCH = os.environ.get("STAGE_MATCH", "agendamento").strip()

# --- Limites ---
MAX_RECORDINGS = int(os.environ.get("MAX_RECORDINGS", "5"))
MAX_DEALS_SCAN = int(os.environ.get("MAX_DEALS_SCAN", "60"))
MAX_BRIEFINGS_PER_POLL = int(os.environ.get("MAX_BRIEFINGS_PER_POLL", "5"))
