"""Auto-sync de calls 3C Plus para deals em Agendamento

Roda a cada 5 minutos (GitHub Actions). Procura deals que entraram
em "Agendamento" SEM briefing ainda, busca as calls na 3C Plus
e cria as atividades automaticamente. Andreia depois processa.
"""
import requests
import logging
import os
from datetime import datetime, timedelta

log = logging.getLogger("3c_sync")
logging.basicConfig(level=logging.INFO, format="[3C Sync] %(message)s")

PIPEDRIVE_TOKEN = os.environ.get("PIPEDRIVE_TOKEN", "").strip()
PIPEDRIVE_BASE = "https://api.pipedrive.com/v1"
THREE_C_TOKEN = os.environ.get("THREE_C_PLUS_TOKEN", "").strip()
THREE_C_BASE = "https://3c.plus/api/v1"


def get_agendamento_stage_ids():
    """Acha as etapas com nome contendo 'agendamento'"""
    r = requests.get(f"{PIPEDRIVE_BASE}/stages", params={"api_token": PIPEDRIVE_TOKEN}, timeout=30)
    r.raise_for_status()
    stages = (r.json() or {}).get("data") or []

    ids = []
    for s in stages:
        if "agendamento" in str(s.get("name") or "").lower():
            ids.append(s.get("id"))
            log.info(f"Etapa encontrada: {s.get('name')} (id={s.get('id')})")

    return ids


def get_deals_in_agendamento():
    """Busca deals em Agendamento que NÃO têm briefing"""
    stage_ids = get_agendamento_stage_ids()
    if not stage_ids:
        log.warning("Nenhuma etapa 'Agendamento' encontrada")
        return []

    deals = []
    for sid in stage_ids:
        r = requests.get(
            f"{PIPEDRIVE_BASE}/deals",
            params={
                "api_token": PIPEDRIVE_TOKEN,
                "stage_id": sid,
                "status": "open",
                "sort": "update_time DESC",
                "limit": 50
            },
            timeout=30
        )
        r.raise_for_status()
        deals.extend((r.json() or {}).get("data") or [])

    # Filtra: só os que entraram em Agendamento nos últimos 2 horas E não têm briefing
    cutoff = (datetime.utcnow() - timedelta(hours=2)).isoformat()

    result = []
    for d in deals:
        # Acha a atividade de transição pra Agendamento (update_time >= cutoff)
        if d.get("update_time") and d.get("update_time") >= cutoff:
            # Checa se tem briefing (procura nota com "BRIEFING COMERCIAL")
            notes_r = requests.get(
                f"{PIPEDRIVE_BASE}/notes",
                params={"api_token": PIPEDRIVE_TOKEN, "deal_id": d.get("id")},
                timeout=30
            )
            notes = (notes_r.json() or {}).get("data") or []
            has_briefing = any("BRIEFING COMERCIAL" in str(n.get("content") or "").upper() for n in notes)

            if not has_briefing:
                result.append(d)
                log.info(f"Deal #{d.get('id')} ({d.get('title')}) pronto pra sync")

    return result


def get_person_phone(person_id):
    """Pega o telefone da pessoa"""
    r = requests.get(
        f"{PIPEDRIVE_BASE}/persons/{person_id}",
        params={"api_token": PIPEDRIVE_TOKEN},
        timeout=30
    )
    r.raise_for_status()
    person = (r.json() or {}).get("data") or {}

    phone = None
    if person.get("phone"):
        # phone é uma lista de objetos {value, primary}
        phones = person.get("phone") or []
        if isinstance(phones, list) and len(phones) > 0:
            phone = phones[0].get("value") if isinstance(phones[0], dict) else phones[0]

    return phone


def search_calls_in_3c(phone):
    """Busca calls na 3C Plus"""
    if not phone:
        return []

    seven_days_ago = (datetime.utcnow() - timedelta(days=7)).date().isoformat()

    r = requests.get(
        f"{THREE_C_BASE}/calls",
        params={
            "api_token": THREE_C_TOKEN,
            "number": phone,
            "start_date": seven_days_ago,
            "limit": 50
        },
        timeout=30
    )
    r.raise_for_status()
    return (r.json() or {}).get("data") or []


def create_activity_in_pipedrive(deal_id, call):
    """Cria atividade no deal"""
    body = {
        "deal_id": deal_id,
        "type": "call",
        "subject": f"Call 3C Plus - {call.get('agent') or 'SDR'} ({call.get('call_date')})",
        "note": f"""Gravação da 3C Plus

Número: {call.get('number')}
Agente: {call.get('agent')}
Duração: {call.get('speaking_time') or 'N/A'}
Status: {call.get('readable_status_text')}

Link da gravação: {call.get('recording')}""",
        "location": call.get('recording'),
        "add_time": call.get('call_date')
    }

    r = requests.post(
        f"{PIPEDRIVE_BASE}/activities",
        params={"api_token": PIPEDRIVE_TOKEN},
        json=body,
        timeout=30
    )
    r.raise_for_status()
    return (r.json() or {}).get("data", {}).get("id")


def sync_deal(deal):
    """Sincroniza um deal: busca calls na 3C e cria atividades"""
    deal_id = deal.get("id")
    person_id = deal.get("person_id", {}).get("value") or deal.get("person_id")

    if not person_id:
        log.warning(f"Deal #{deal_id}: sem pessoa associada")
        return False

    # Pega telefone
    phone = get_person_phone(person_id)
    if not phone:
        log.warning(f"Deal #{deal_id}: pessoa sem telefone")
        return False

    log.info(f"Deal #{deal_id}: buscando calls para {phone}")

    # Busca na 3C
    calls = search_calls_in_3c(phone)
    if not calls:
        log.info(f"Deal #{deal_id}: nenhuma call encontrada")
        return True

    # Cria atividades
    created = 0
    for call in calls:
        if call.get('recording'):  # Só se tem gravação
            try:
                aid = create_activity_in_pipedrive(deal_id, call)
                if aid:
                    created += 1
                    log.info(f"Deal #{deal_id}: atividade criada (id={aid})")
            except Exception as e:
                log.error(f"Deal #{deal_id}: erro ao criar atividade: {e}")

    log.info(f"Deal #{deal_id}: {created} atividade(s) criada(s). Andreia vai processar.")
    return True


def main():
    """Main"""
    if not PIPEDRIVE_TOKEN:
        log.error("PIPEDRIVE_TOKEN não configurado")
        return

    if not THREE_C_TOKEN:
        log.error("THREE_C_PLUS_TOKEN não configurado")
        return

    log.info("Iniciando sync...")

    try:
        deals = get_deals_in_agendamento()
        if not deals:
            log.info("Nenhum deal pra sincronizar")
            return

        log.info(f"Encontrados {len(deals)} deal(s) pra sincronizar")

        for deal in deals:
            try:
                sync_deal(deal)
            except Exception as e:
                log.error(f"Erro ao sincronizar deal #{deal.get('id')}: {e}")

    except Exception as e:
        log.error(f"Erro geral: {e}")


if __name__ == "__main__":
    main()
