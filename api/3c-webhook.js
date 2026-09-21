/**
 * Webhook receiver para 3C Plus
 * Recebe call-history-was-created, extrai gravação e número
 * Cria atividade no Pipedrive pra Andreia processar depois
 */

const PIPEDRIVE_TOKEN = process.env.PIPEDRIVE_TOKEN
const PIPEDRIVE_BASE = 'https://api.pipedrive.com/v1'

async function findPersonByPhone(number) {
  /**Busca pessoa no Pipedrive pelo número de telefone */
  const params = new URLSearchParams({
    api_token: PIPEDRIVE_TOKEN,
    term: number,
    search_across: 'phone'
  })

  const r = await fetch(`${PIPEDRIVE_BASE}/persons/search?${params}`, { timeout: 30000 })
  const data = await r.json()

  if (!data.data || !data.data.items || data.data.items.length === 0) {
    return null
  }

  const person = data.data.items[0].person
  return { id: person.id, name: person.name }
}

async function getDealFromPerson(personId) {
  /** Pega o primeiro negócio aberto da pessoa */
  const params = new URLSearchParams({
    api_token: PIPEDRIVE_TOKEN,
    person_id: personId,
    status: 'open',
    limit: 1
  })

  const r = await fetch(`${PIPEDRIVE_BASE}/deals?${params}`, { timeout: 30000 })
  const data = await r.json()

  if (!data.data || data.data.length === 0) {
    return null
  }

  return data.data[0].id
}

async function createActivity(dealId, callData) {
  /** Cria atividade de call no negócio com link da gravação */
  const body = {
    deal_id: dealId,
    type: 'call',
    subject: `Call 3C Plus - ${callData.agent || 'SDR'} (${callData.call_date})`,
    note: `Gravação da 3C Plus\n\nNúmero: ${callData.number}\nAgente: ${callData.agent}\nDuração: ${callData.speaking_time || 'N/A'}\nStatus: ${callData.readable_status_text}\n\nLink da gravação: ${callData.recording}`,
    location: callData.recording,  // a URL também vai como location (Andreia acha lá)
    add_time: new Date().toISOString()
  }

  const r = await fetch(`${PIPEDRIVE_BASE}/activities?api_token=${PIPEDRIVE_TOKEN}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    timeout: 30000
  })

  const data = await r.json()
  return data.data && data.data.id ? data.data.id : null
}

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' })
  }

  try {
    const event = req.body

    // Valida estrutura mínima
    if (!event.type || !event.call) {
      return res.status(400).json({ error: 'Invalid payload structure' })
    }

    // Só processa call-history-was-created
    if (event.type !== 'call-history-was-created') {
      return res.status(200).json({ status: 'ignored', reason: 'Event type not call-history-was-created' })
    }

    const call = event.call

    // Valida campos essenciais
    if (!call.number || !call.recording) {
      return res.status(400).json({ error: 'Missing number or recording URL' })
    }

    // Log
    console.log(`[3C Webhook] Call recebida: ${call.number} | Recording: ${call.recording}`)

    // Procura pessoa pelo número
    const person = await findPersonByPhone(call.number)
    if (!person) {
      console.log(`[3C Webhook] Nenhuma pessoa encontrada para: ${call.number}`)
      return res.status(200).json({
        status: 'person_not_found',
        number: call.number,
        note: 'Número não encontrado no Pipedrive'
      })
    }

    // Pega negócio aberto da pessoa
    const dealId = await getDealFromPerson(person.id)
    if (!dealId) {
      console.log(`[3C Webhook] Nenhum negócio aberto para: ${person.name}`)
      return res.status(200).json({
        status: 'deal_not_found',
        person: person.name,
        note: 'Pessoa encontrada mas sem negócio aberto'
      })
    }

    // Cria atividade
    const activityId = await createActivity(dealId, call)
    if (!activityId) {
      return res.status(500).json({ error: 'Failed to create activity' })
    }

    console.log(`[3C Webhook] ✅ Atividade criada: ${activityId} | Deal: ${dealId} | Pessoa: ${person.name}`)

    return res.status(200).json({
      status: 'success',
      activity_id: activityId,
      deal_id: dealId,
      person: person.name,
      number: call.number,
      message: 'Call registrada. Andreia vai processar.'
    })

  } catch (err) {
    console.error('[3C Webhook] Erro:', err.message)
    return res.status(500).json({ error: err.message })
  }
}
