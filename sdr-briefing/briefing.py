"""Geração do briefing comercial (SPIN + BANT) a partir das ligações do lead.

Chama o Gemini pela API do Google AI Studio (REST direto, nível grátis).

Preserva as REGRAS ANTI-ALUCINAÇÃO:
- Nunca inventar: só fatos reais ditos no áudio; o que não foi dito vira
  'Nao declarado na ligacao'.
- Áudio em silêncio / sem qualificação -> ERRO_AUDIO_INVALIDO -> NENHUMA nota é criada.
- Consolida TODAS as ligações do histórico (não só a última).
"""
import base64
import logging
import time
import requests
import config
import pipedrive

log = logging.getLogger("briefing")

# ⚠️ Prompt validado — não afrouxar as regras anti-alucinação.
PROMPT = """Voce e um Diretor de Vendas e Inteligencia Comercial especialista no mercado de Locacao de Equipamentos.
Sua tarefa e analisar TODAS as gravacoes de audio de qualificacao anexadas (elas representam diferentes contatos ou tentativas com o mesmo lead) e gerar um Briefing de Vendas consolidado e unificado de alta performance para o Closer (vendedor) baseado nas metodologias SPIN e BANT.

REGRAS CRITICAS ABSOLUTAS:
1. Se TODAS as gravacoes de audio fornecidas estiverem em silencio, forem invalidas, corrompidas ou sem dialogo real de qualificacao, responda EXATAMENTE E APENAS com a palavra: ERRO_AUDIO_INVALIDO. Nao gere absolutamente nada alem disso.
2. Consolide as informacoes extraidas de todas as ligacoes: se um dado (ex: nome do decisor ou dor do cliente) foi dito na primeira ligacao mas nao na segunda, use o dado que foi falado! O objetivo e preencher o maximo possivel dos quadros de SPIN e BANT unificando todo o historico de ligacoes fornecidas.
3. NUNCA, SOB NENHUMA HIPOTESE, INVENTE OU CRIE dados ficticios. Voce so pode colocar fatos reais ditos nos audios. Se alguma informacao nao tiver sido dita pelo cliente em NENHUMA das ligacoes, escreva apenas 'Nao declarado na ligacao' naquele topico.

O briefing deve ser altamente analitico, conciso e estruturado exatamente com os seguintes topicos (use tags HTML como <h3>, <h4>, <ul>, <li>, <b> para formatar, ja que o texto sera anexado como Nota no Pipedrive):

<h3>📋 BRIEFING COMERCIAL SPIN & BANT - [NOME DA EMPRESA]</h3>
<p><i>Briefing consolidado via IA a partir de todas as ligacoes de qualificacao do SDR no historico.</i></p>
<hr />
<h4>🎯 Filtro de Qualificacao (BANT)</h4>
<ul>
<li><b>B - Budget (Orcamento):</b> [Qual a verba declarada, limites de investimento ou 'Nao declarado na ligacao']</li>
<li><b>A - Authority (Autoridade):</b> [Cargo do contato, quem toma a decisao de contratacao ou 'Nao declarado na ligacao']</li>
<li><b>N - Need (Necessidade):</b> [Qual a necessidade comercial ou dor prioritaria que buscam sanar ou 'Nao declarado na ligacao']</li>
<li><b>T - Timeline (Cronograma):</b> [Prazo para inicio, urgencia de implantacao ou 'Nao declarado na ligacao']</li>
</ul>
<hr />
<h4>🔍 Diagnostico Comercial (SPIN Selling)</h4>
<ul>
<li><b>S - Situacao:</b> [Cenario atual da locadora, tamanho da frota, faturamento atual, equipe ou 'Nao declarado na ligacao']</li>
<li><b>P - Problema:</b> [Dores especificas, gargalos da operacao, taxa de ociosidade, reclamacoes declaradas ou 'Nao declarado na ligacao']</li>
<li><b>I - Implicacao:</b> [As consequencias graves se o problema persistir: custos de ociosidade, perda de faturamento ou 'Nao declarado na ligacao']</li>
<li><b>N - Necessidade de Solucao:</b> [Os beneficios, ganhos e metas que o cliente deseja alcancar ao contratar a solucao ou 'Nao declarado na ligacao']</li>
</ul>
<hr />
<h4>🚀 Recomendacoes para o Closer</h4>
<ul>
<li><b>Gatilhos Mentais Indicados:</b> [Quais usar na reuniao com base nas dores identificadas]</li>
<li><b>Como Ancorar o Valor:</b> [Calculo ou conexao com o ROI baseado na taxa de ociosidade e metas]</li>
<li><b>Cases de Sucesso Sugeridos:</b> [Quais cases da ODuo citar para este nicho]</li>
</ul>

Seja extremamente profissional, direto e comercialmente focado. Baseie-se integralmente no conteudo falado no audio."""


def _generate(recordings):
    """Baixa os áudios, envia todos juntos ao Gemini (REST) e retorna o briefing."""
    parts = []
    for i, rec in enumerate(recordings[: config.MAX_RECORDINGS], 1):
        try:
            audio = requests.get(rec["url"], timeout=90).content
            b64 = base64.b64encode(audio).decode("ascii")
            parts.append({"inline_data": {"mime_type": "audio/mpeg", "data": b64}})
            log.info("Audio %d/%d baixado (%d bytes): %s", i, len(recordings), len(audio), rec["subject"])
        except Exception as e:
            log.warning("Falha ao baixar audio %s: %s", rec["url"], e)

    if not parts:
        return None

    parts.append({"text": PROMPT})
    url = f"{config.GEMINI_BASE}/models/{config.GEMINI_MODEL}:generateContent?key={config.GEMINI_API_KEY}"
    body = {"contents": [{"parts": parts}]}

    last_err = None
    for attempt in range(1, 4):
        try:
            r = requests.post(url, json=body, timeout=180)
            r.raise_for_status()
            data = r.json()
            text = (data["candidates"][0]["content"]["parts"][0]["text"] or "").strip()
            if "ERRO_AUDIO_INVALIDO" in text.upper():
                return "ERRO_AUDIO_INVALIDO"
            return text
        except Exception as e:
            last_err = e
            log.warning("Gemini tentativa %d falhou: %s", attempt, e)
            time.sleep(3 * attempt)
    raise RuntimeError(f"Gemini falhou apos 3 tentativas: {last_err}")


def process_deal(deal_id, skip_if_briefed=True):
    """Fluxo completo para um negócio: ligações -> briefing -> nota fixada."""
    if skip_if_briefed and pipedrive.has_briefing_note(deal_id):
        log.info("Negocio %s ja possui briefing. Pulando.", deal_id)
        return {"status": "already_briefed", "deal_id": deal_id}

    log.info("Processando negocio %s...", deal_id)
    recordings = pipedrive.find_call_recordings(pipedrive.get_activities(deal_id))

    if not recordings:
        log.info("Negocio %s: nenhuma gravacao de ligacao encontrada.", deal_id)
        return {"status": "no_recordings", "deal_id": deal_id}

    briefing = _generate(recordings)

    if briefing is None:
        log.warning("Negocio %s: nao foi possivel baixar nenhum audio.", deal_id)
        return {"status": "download_failed", "deal_id": deal_id}

    if briefing == "ERRO_AUDIO_INVALIDO":
        log.info("Negocio %s: audios sem qualificacao real. Nenhuma nota criada.", deal_id)
        return {"status": "invalid_audio", "deal_id": deal_id}

    pipedrive.add_pinned_note(deal_id, briefing)
    log.info("Negocio %s: briefing anexado como nota fixada. OK", deal_id)
    return {"status": "briefing_posted", "deal_id": deal_id}
