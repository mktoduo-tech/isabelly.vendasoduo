"""Helpers da API do Pipedrive (v1): etapas, negócios, atividades/ligações e notas."""
import re
import logging
import requests
import config

log = logging.getLogger("pipedrive")

RECORDING_RE = re.compile(
    r'https?://[^\s"\'<>]+(?:mp3|wav|pi4com|api4com|gravacao|recording|call)[^\s"\'<>]*', re.I
)
URL_RE = re.compile(r'https?://[^\s"\'<>]+')
SKIP_HOSTS = ("meet.google.com", "zoom.us", "teams.microsoft.com", "teams.live.com")
BRIEFING_MARKER = "BRIEFING COMERCIAL"  # dedup: reconhece negócio já com briefing


def _params(extra=None):
    p = {"api_token": config.PIPEDRIVE_TOKEN}
    if extra:
        p.update(extra)
    return p


def get_stage_ids_matching(term="agendamento"):
    """IDs das etapas cujo nome CONTÉM 'term' (ex.: 'Agendamento'), em qualquer funil."""
    r = requests.get(f"{config.PIPEDRIVE_BASE}/stages", params=_params(), timeout=30)
    r.raise_for_status()
    stages = (r.json() or {}).get("data") or []
    t = term.strip().lower()
    ids, names = set(), []
    for s in stages:
        name = str(s.get("name") or "")
        if t in name.lower():
            ids.add(s.get("id"))
            names.append(name)
    if names:
        log.info("Etapas casando '%s': %s", term, ", ".join(sorted(set(names))))
    return ids


def get_open_deals_in_stages(stage_ids, limit_per_stage=60):
    """Negócios ABERTOS que estão nas etapas informadas (mais recentes primeiro)."""
    deals = []
    for sid in stage_ids:
        r = requests.get(
            f"{config.PIPEDRIVE_BASE}/deals",
            params=_params({"status": "open", "stage_id": sid,
                            "sort": "update_time DESC", "limit": limit_per_stage}),
            timeout=30,
        )
        r.raise_for_status()
        deals.extend((r.json() or {}).get("data") or [])
    return deals


def get_activities(deal_id):
    r = requests.get(
        f"{config.PIPEDRIVE_BASE}/deals/{deal_id}/activities", params=_params(), timeout=30
    )
    r.raise_for_status()
    return (r.json() or {}).get("data") or []


def get_notes(deal_id):
    r = requests.get(
        f"{config.PIPEDRIVE_BASE}/notes", params=_params({"deal_id": deal_id}), timeout=30
    )
    r.raise_for_status()
    return (r.json() or {}).get("data") or []


def has_briefing_note(deal_id):
    for n in get_notes(deal_id):
        if BRIEFING_MARKER in str(n.get("content") or "").upper():
            return True
    return False


def find_call_recordings(activities):
    recordings, seen = [], set()
    for act in activities or []:
        note = str(act.get("note") or "")
        subject = str(act.get("subject") or "")
        location = str(act.get("location") or "")

        url = None
        m = RECORDING_RE.search(note)
        if m:
            url = m.group(0)
        else:
            for src in (location, subject):
                m2 = URL_RE.search(src)
                if m2:
                    url = m2.group(0)
                    break

        if not url or any(h in url for h in SKIP_HOSTS) or url in seen:
            continue
        seen.add(url)
        recordings.append({"subject": subject, "url": url})
    return recordings


def add_pinned_note(deal_id, html):
    body = {"deal_id": int(deal_id), "content": html, "pinned_to_deal_flag": 1}
    r = requests.post(f"{config.PIPEDRIVE_BASE}/notes", params=_params(), json=body, timeout=30)
    r.raise_for_status()
    return (r.json() or {}).get("data")
