/**
 * Backfill de calls da 3C Plus para um deal do Pipedrive
 * Quando SDR cria um novo lead, usa esse endpoint pra buscar todas as calls
 * daquele número nos últimos 7 dias e cria as atividades
 *
 * Uso: GET /api/3c-backfill?phone=11999999999&deal_id=12345
 */

const PIPEDRIVE_TOKEN = process.env.PIPEDRIVE_TOKEN
const PIPEDRIVE_BASE = 'https://api.pipedrive.com/v1'
const THREE_C_TOKEN = process.env.THREE_C_PLUS_TOKEN
const THREE_C_BASE = 'https://3c.plus/api/v1'

async function searchCallsByPhone(phone) {
  /** Busca todas as calls da 3C Plus com esse número (últimos 7 dias) */

  // Data de 7 dias atrás
  const sevenDaysAgo = new Date()
  sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7)
  const startDate = sevenDaysAgo.toISOString().split('T')[0]

  const params = new URLSearchParams({
    api_token: THREE_C_TOKEN,
    number: phone,
    start_date: startDate,
    limit: 50
  })

  const r = await fetch(`${THREE_C_BASE}/calls?${params}`, { timeout: 30000 })
  const data = await r.json()

  if (!data.data || data.data.length === 0) {
    return []
  }

  return data.data
}

async function createActivity(dealId, call) {
  /** Cria atividade no deal com os dados da call */
  const body = {
    deal_id: dealId,
    type: 'call',
    subject: `Call 3C Plus - ${call.agent || 'SDR'} (${call.call_date})`,
    note: `Gravação da 3C Plus\n\nNúmero: ${call.number}\nAgente: ${call.agent}\nDuração: ${call.speaking_time || 'N/A'}\nStatus: ${call.readable_status_text}\n\nLink da gravação: ${call.recording}`,
    location: call.recording,
    add_time: call.call_date
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
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' })
  }

  try {
    const { phone, deal_id } = req.query

    // Valida parâmetros
    if (!phone || !deal_id) {
      return res.status(400).json({
        error: 'Missing required parameters: phone, deal_id',
        example: '/api/3c-backfill?phone=11999999999&deal_id=12345'
      })
    }

    if (!THREE_C_TOKEN) {
      return res.status(500).json({ error: 'THREE_C_PLUS_TOKEN not configured' })
    }

    console.log(`[3C Backfill] Buscando calls para: ${phone} | Deal: ${deal_id}`)

    // Busca calls na 3C Plus
    const calls = await searchCallsByPhone(phone)

    if (calls.length === 0) {
      return res.status(200).json({
        status: 'no_calls_found',
        phone,
        deal_id,
        message: 'Nenhuma call encontrada para este número nos últimos 7 dias'
      })
    }

    // Cria atividades pra cada call
    const createdActivities = []
    for (const call of calls) {
      if (call.recording) {  // Só cria atividade se tem gravação
        const activityId = await createActivity(deal_id, call)
        if (activityId) {
          createdActivities.push({
            activity_id: activityId,
            call_date: call.call_date,
            duration: call.speaking_time,
            agent: call.agent
          })
        }
      }
    }

    console.log(`[3C Backfill] ✅ ${createdActivities.length} atividades criadas para deal ${deal_id}`)

    return res.status(200).json({
      status: 'success',
      phone,
      deal_id,
      total_calls_found: calls.length,
      activities_created: createdActivities.length,
      activities: createdActivities,
      message: `${createdActivities.length} call(s) vinculada(s) ao deal. Andreia vai processar.`
    })

  } catch (err) {
    console.error('[3C Backfill] Erro:', err.message)
    return res.status(500).json({ error: err.message })
  }
}
