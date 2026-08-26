"""Roda UMA varredura e sai (chamado pelo GitHub Actions a cada X minutos).

REGRA DE GATILHO: só olha negócios que estão na etapa de AGENDAMENTO
(quando o SDR marcou a reunião). Para cada um que tem ligação e ainda não tem
briefing, gera o briefing (SPIN+BANT) e anexa como nota fixada no card.
Dedup evita repetir.
"""
import logging
import config
import pipedrive
import briefing

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("poll")


def main():
    if not config.PIPEDRIVE_TOKEN or not config.GEMINI_API_KEY:
        raise SystemExit("ERRO: defina os secrets PIPEDRIVE_TOKEN e GEMINI_API_KEY.")

    # 1) Descobre a(s) etapa(s) de "Agendamento"
    stage_ids = pipedrive.get_stage_ids_matching(config.STAGE_MATCH)
    if not stage_ids:
        log.warning(
            "Nenhuma etapa com nome contendo '%s' foi encontrada no Pipedrive. "
            "Nada a fazer. (Confira o nome exato da etapa.)", config.STAGE_MATCH
        )
        return

    # 2) Só os negócios abertos nessa etapa
    deals = pipedrive.get_open_deals_in_stages(stage_ids, config.MAX_DEALS_SCAN)
    log.info("Negocios abertos na etapa de agendamento: %d", len(deals))

    briefed = 0
    for d in deals:
        if briefed >= config.MAX_BRIEFINGS_PER_POLL:
            log.info("Limite de %d briefings por rodada atingido.", config.MAX_BRIEFINGS_PER_POLL)
            break
        deal_id = d.get("id")
        if not deal_id:
            continue
        try:
            if pipedrive.has_briefing_note(deal_id):
                continue
            if not pipedrive.find_call_recordings(pipedrive.get_activities(deal_id)):
                continue
            res = briefing.process_deal(deal_id, skip_if_briefed=False)
            log.info("Negocio %s -> %s", deal_id, res.get("status"))
            if res.get("status") == "briefing_posted":
                briefed += 1
        except Exception as e:
            log.exception("Erro no negocio %s: %s", deal_id, e)

    log.info("Rodada concluida. Briefings criados nesta rodada: %d", briefed)


if __name__ == "__main__":
    main()
