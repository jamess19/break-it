import { useEffect, useRef, useState } from 'react'
import { getHealth, sendChat } from './api'

interface DisplayMessage {
  role: 'user' | 'assistant'
  content: string
}

// session_id giữ qua reload trong 1 trình duyệt — khớp cách backend lưu history theo
// session_id trong Redis (app/services/session.py), không phải auth thật.
function getSessionId(): string {
  const key = 'ops-agent-session-id'
  let id = localStorage.getItem(key)
  if (!id) {
    id = crypto.randomUUID()
    localStorage.setItem(key, id)
  }
  return id
}

export default function App() {
  const [sessionId] = useState(getSessionId)
  const [messages, setMessages] = useState<DisplayMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [health, setHealth] = useState<string | null>(null)
  const [lastCost, setLastCost] = useState<number | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    getHealth()
      .then((h) => setHealth(`${h.provider} / ${h.model}`))
      .catch(() => setHealth('không kết nối được backend'))
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function handleSend() {
    const text = input.trim()
    if (!text || loading) return
    setInput('')
    setError(null)
    setMessages((prev) => [...prev, { role: 'user', content: text }])
    setLoading(true)
    try {
      const res = await sendChat(sessionId, text)
      setMessages((prev) => [...prev, { role: 'assistant', content: res.reply }])
      setLastCost(res.cost_usd)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto flex h-screen max-w-2xl flex-col p-4">
      <header className="mb-3 flex items-center justify-between border-b pb-2">
        <h1 className="text-lg font-semibold">Personal Ops Agent</h1>
        <span className="text-xs text-gray-500">{health ?? 'đang kiểm tra...'}</span>
      </header>

      <div className="flex-1 overflow-y-auto space-y-3 pr-1">
        {messages.length === 0 && (
          <p className="text-sm text-gray-400">
            Nhắn gì đó, vd &quot;thêm task viết báo cáo, deadline thứ 6&quot;.
          </p>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`rounded-lg px-3 py-2 text-sm whitespace-pre-wrap ${
              m.role === 'user'
                ? 'ml-auto max-w-[80%] bg-blue-600 text-white'
                : 'mr-auto max-w-[80%] bg-gray-100 text-gray-900'
            }`}
          >
            {m.content}
          </div>
        ))}
        {loading && <p className="text-sm text-gray-400">đang xử lý...</p>}
        {error && <p className="text-sm text-red-600">Lỗi: {error}</p>}
        <div ref={bottomRef} />
      </div>

      <div className="mt-3 flex gap-2 border-t pt-3">
        <input
          className="flex-1 rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          placeholder="Nhắn tin..."
          disabled={loading}
        />
        <button
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          onClick={handleSend}
          disabled={loading || !input.trim()}
        >
          Gửi
        </button>
      </div>
      {lastCost != null && (
        <p className="mt-1 text-right text-xs text-gray-400">chi phí lượt vừa rồi: ${lastCost.toFixed(6)}</p>
      )}
    </div>
  )
}
