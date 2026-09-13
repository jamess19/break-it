// Typed fetch wrapper — khớp đúng app/api/schemas.py (ChatRequest/ChatResponse).
// Không tự bịa field: đây là hợp đồng HTTP thật của backend, sửa ở app/api/schemas.py
// thì sửa lại đây theo, không suy đoán.

export interface ChatResponse {
  session_id: string
  reply: string
  steps: number
  tool_calls: number
  usage: { prompt_tokens: number; completion_tokens: number; total_tokens: number } | null
  cost_usd: number | null
  trace: Array<Record<string, unknown>>
}

export interface HealthResponse {
  ok: boolean
  provider: string
  model: string
}

const BASE = '' // relative — Vite dev proxy (vite.config.ts) hoặc cùng origin lúc deploy

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`${res.status} ${res.statusText}: ${text}`)
  }
  return res.json() as Promise<T>
}

export function sendChat(sessionId: string, message: string): Promise<ChatResponse> {
  return postJson<ChatResponse>('/chat', { session_id: sessionId, message })
}

export async function getHealth(): Promise<HealthResponse> {
  const res = await fetch(`${BASE}/health`)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<HealthResponse>
}
