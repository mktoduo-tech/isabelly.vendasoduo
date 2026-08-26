"""Configuração via variáveis de ambiente (GitHub Actions Secrets)."""
import os

# --- Pipedrive ---
PIPEDRIVE_TOKEN = os.environ.get("PIPEDRIVE_TOKEN", "").strip()
PIPEDRIVE_BASE = "https://api.pipedrive.com/v1"

# --- Gemini (Google AI Studio - nível grátis) ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash").strip()
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"

# --- Comportamento / limites ---
MAX_RECORDINGS = int(os.environ.get("MAX_RECORDINGS", "5"))          # áudios por negócio
MAX_DEALS_SCAN = int(os.environ.get("MAX_DEALS_SCAN", "40"))         # negócios olhados por rodada
MAX_BRIEFINGS_PER_POLL = int(os.environ.get("MAX_BRIEFINGS_PER_POLL", "5"))  # briefings por rodada
