import { useState, useRef, useEffect } from 'react'
import { Send, Sparkle, ChevDown } from '../components/Icons'
import { askChat, getChatHistory, getChatStatus, getUploads } from '../api'

export default function ChatPage() {
  const [messages, setMessages] = useState([
    { role: 'ai', text: "Hi! I'm Verso AI. Select a document above to start chatting.", sources: [] },
  ])
  const [input, setInput] = useState('')
  const [typing, setTyping] = useState(false)
  const [uploads, setUploads] = useState([])
  const [uploadId, setUploadId] = useState(null)
  const [qaReady, setQaReady] = useState(false)
  const [remaining, setRemaining] = useState(null)
  const endRef = useRef(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, typing])

  // Fetch uploads on mount
  useEffect(() => {
    getUploads()
      .then((list) => {
        setUploads(list)
        if (list.length > 0) setUploadId(list[0].id)
      })
      .catch(() => {})
  }, [])

  // When uploadId changes, load status + history
  useEffect(() => {
    if (!uploadId) return

    const doc = uploads.find((u) => u.id === uploadId)
    const name = doc?.filename || 'Document'

    getChatStatus(uploadId)
      .then((s) => {
        setQaReady(s.qa_ready)
        setRemaining(s.remaining)
      })
      .catch(() => setQaReady(false))

    getChatHistory(uploadId)
      .then((history) => {
        const restored = history.flatMap((h) => [
          { role: 'user', text: h.user_message },
          { role: 'ai', text: h.ai_response, sources: h.sources },
        ])
        setMessages([
          { role: 'ai', text: `Ask me anything about ${name}!`, sources: [] },
          ...restored,
        ])
      })
      .catch(() => {
        setMessages([
          { role: 'ai', text: `Ask me anything about ${name}!`, sources: [] },
        ])
      })
  }, [uploadId])

  const send = async () => {
    if (!input.trim() || !uploadId || !qaReady || typing) return
    const userMsg = input.trim()
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', text: userMsg }])
    setTyping(true)

    try {
      const res = await askChat(uploadId, userMsg)
      setMessages((prev) => [
        ...prev,
        { role: 'ai', text: res.answer, sources: res.sources },
      ])
      setRemaining(res.limit - res.exchange_count)
    } catch (err) {
      const detail = err.response?.data?.detail || 'Something went wrong. Please try again.'
      setMessages((prev) => [
        ...prev,
        { role: 'ai', text: detail, sources: [], error: true },
      ])
    } finally {
      setTyping(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  const inputDisabled = !uploadId || !qaReady || (remaining !== null && remaining <= 0)

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <div className="flex items-center gap-3 px-6 py-4 border-b border-border bg-surface/50 backdrop-blur-sm">
        <div className="w-9 h-9 rounded-full bg-primary/10 flex items-center justify-center text-primary">
          <Sparkle />
        </div>
        <div className="flex-1 min-w-0">
          <h2 className="text-sm font-semibold">Ask Verso</h2>
          {uploads.length > 0 ? (
            <div className="relative">
              <select
                value={uploadId || ''}
                onChange={(e) => setUploadId(Number(e.target.value))}
                className="text-text-muted text-xs bg-transparent outline-none cursor-pointer appearance-none pr-4 max-w-full truncate"
              >
                {uploads.map((u) => (
                  <option key={u.id} value={u.id}>{u.filename}</option>
                ))}
              </select>
              <span className="absolute right-0 top-0.5 pointer-events-none text-text-muted"><ChevDown /></span>
            </div>
          ) : (
            <p className="text-text-muted text-xs">No documents uploaded yet</p>
          )}
        </div>
        {remaining !== null && (
          <span className="text-[10px] text-text-muted whitespace-nowrap">{remaining} left</span>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} fade-up`}
            style={{ animationDelay: `${i * 0.05}s` }}
          >
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                msg.role === 'user'
                  ? 'bg-surface-alt text-text rounded-br-md'
                  : msg.error
                    ? 'bg-danger/10 border border-danger/30 text-danger rounded-bl-md'
                    : 'bg-surface border border-border text-text-secondary rounded-bl-md'
              }`}
            >
              {msg.text}
              {msg.sources?.length > 0 && (
                <div className="flex flex-wrap gap-2 mt-2 pt-2 border-t border-border">
                  {msg.sources.map((s, j) => (
                    <span key={j} className="text-[10px] px-2 py-0.5 rounded-full bg-primary/10 text-primary-light font-mono">
                      {s}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {typing && (
          <div className="flex justify-start">
            <div className="bg-surface border border-border rounded-2xl rounded-bl-md px-4 py-3 flex gap-1.5">
              {[0, 1, 2].map((i) => (
                <div
                  key={i}
                  className="w-2 h-2 rounded-full bg-primary pulse-3"
                  style={{ animationDelay: `${i * 0.2}s` }}
                />
              ))}
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      {/* Input bar */}
      <div className="px-6 py-4 border-t border-border bg-surface/50 backdrop-blur-sm">
        {!qaReady && uploadId && (
          <p className="text-xs text-warning mb-2">Document is still processing. Chat will be available once complete.</p>
        )}
        {remaining !== null && remaining <= 0 && (
          <p className="text-xs text-text-muted mb-2">Exchange limit reached for this document.</p>
        )}
        <div className={`flex items-center gap-3 bg-surface-alt rounded-xl px-4 py-2 border border-border ${inputDisabled ? 'opacity-50' : ''}`}>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={inputDisabled ? 'Chat unavailable' : 'Ask about your document...'}
            disabled={inputDisabled}
            className="flex-1 bg-transparent outline-none text-sm text-text placeholder:text-text-muted/50 disabled:cursor-not-allowed"
          />
          <button
            onClick={send}
            disabled={inputDisabled || !input.trim()}
            className={`p-2 rounded-lg transition-all cursor-pointer ${
              !inputDisabled && input.trim()
                ? 'bg-primary text-white shadow-md shadow-primary/25'
                : 'text-text-muted'
            }`}
          >
            <Send />
          </button>
        </div>
      </div>
    </div>
  )
}
