import { useState, useRef, useEffect, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Send, Sparkle, ChevDown, Mic, MicOff, ArrowL } from '../components/Icons'
import { askChat, getChatHistory, getChatStatus, getChatSummary, getUploads, startNewChatSession } from '../api'
import { getWsBaseUrl, getAuthToken } from '../api/ws'

export default function ChatPage() {
  const [searchParams] = useSearchParams()
  const [messages, setMessages] = useState([
    { role: 'ai', text: "Hi! I'm Verso AI. Select a document above to start chatting.", sources: [] },
  ])
  const [input, setInput] = useState('')
  const [typing, setTyping] = useState(false)
  const [uploads, setUploads] = useState([])
  const [uploadId, setUploadId] = useState(null)
  const [qaReady, setQaReady] = useState(false)
  const [remaining, setRemaining] = useState(null)
  const [limit, setLimit] = useState(null)
  const [summary, setSummary] = useState(null)
  const [pastSummaries, setPastSummaries] = useState([])
  const [listening, setListening] = useState(false)
  const [interimText, setInterimText] = useState('')
  const endRef = useRef(null)
  const recognitionRef = useRef(null)
  const inputBeforeListenRef = useRef('')
  const wsRef = useRef(null)
  const pendingSourcesRef = useRef([])
  const streamingRef = useRef(false)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, typing])

  // Fetch uploads on mount — only show completed documents in chat
  useEffect(() => {
    getUploads()
      .then((list) => {
        const ready = list.filter((u) => u.status === 'done')
        setUploads(ready)
        const paramId = Number(searchParams.get('upload'))
        if (paramId && ready.some((u) => u.id === paramId)) {
          setUploadId(paramId)
        } else if (ready.length > 0) {
          setUploadId(ready[0].id)
        }
      })
      .catch(() => {})
  }, [])

  // Connect/reconnect WebSocket when uploadId changes
  const connectChatWs = useCallback((uid) => {
    if (wsRef.current) {
      try { wsRef.current.close() } catch {}
      wsRef.current = null
    }
    if (!uid) return

    const token = getAuthToken()
    if (!token) return

    try {
      const ws = new WebSocket(`${getWsBaseUrl()}/ws/chat/${uid}?token=${token}`)
      wsRef.current = ws

      ws.onmessage = (evt) => {
        try {
          const msg = JSON.parse(evt.data)
          if (msg.type === 'stream_start') {
            // Store sources but don't show bubble yet — wait for first token
            pendingSourcesRef.current = msg.sources || []
            streamingRef.current = false
          } else if (msg.type === 'token') {
            if (!streamingRef.current) {
              // First token: create the AI bubble and hide typing dots
              streamingRef.current = true
              setTyping(false)
              setMessages((prev) => [...prev, { role: 'ai', text: msg.content, sources: pendingSourcesRef.current }])
            } else {
              // Subsequent tokens: append to last message
              setMessages((prev) => {
                const updated = [...prev]
                const last = updated[updated.length - 1]
                if (last && last.role === 'ai') {
                  updated[updated.length - 1] = { ...last, text: last.text + msg.content }
                }
                return updated
              })
            }
          } else if (msg.type === 'generating_summary') {
            setTyping(true)
          } else if (msg.type === 'stream_end') {
            setTyping(false)
            const newRemaining = msg.limit - msg.exchange_count
            setRemaining(newRemaining)
            setLimit(msg.limit)
            if (msg.summary) {
              setSummary(msg.summary)
            }
          } else if (msg.type === 'error') {
            setTyping(false)
            setMessages((prev) => [
              ...prev,
              { role: 'ai', text: msg.detail, sources: [], error: true },
            ])
          }
        } catch {}
      }

      ws.onerror = () => { wsRef.current = null }
      ws.onclose = () => { wsRef.current = null }
    } catch {
      wsRef.current = null
    }
  }, [])

  // When uploadId changes, load status + history + connect WS
  useEffect(() => {
    if (!uploadId) return

    const doc = uploads.find((u) => u.id === uploadId)
    const name = doc?.filename || 'Document'

    const loadChat = async () => {
      try {
        const status = await getChatStatus(uploadId)
        setQaReady(status.qa_ready)
        setRemaining(status.remaining)
        setLimit(status.limit)

        let summaryText = null
        try {
          const res = await getChatSummary(uploadId)
          const allSummaries = res.summaries || []
          setPastSummaries(status.has_summary ? allSummaries.slice(0, -1) : allSummaries)
          if (status.has_summary && allSummaries.length > 0) {
            summaryText = allSummaries[allSummaries.length - 1].summary
            setSummary(summaryText)
          } else {
            setSummary(null)
          }
        } catch {
          setPastSummaries([])
          setSummary(null)
        }

        if (status.qa_ready) connectChatWs(uploadId)

        const history = await getChatHistory(uploadId)
        const restored = history.flatMap((h) => [
          { role: 'user', text: h.user_message },
          { role: 'ai', text: h.ai_response, sources: h.sources },
        ])

        if (restored.length === 0 && summaryText) {
          setMessages([
            { role: 'ai', text: `Here's a summary of your conversation about ${name}:`, sources: [] },
          ])
        } else {
          setMessages([
            { role: 'ai', text: `Ask me anything about ${name}!`, sources: [] },
            ...restored,
          ])
        }
      } catch {
        setMessages([
          { role: 'ai', text: `Ask me anything about ${name}!`, sources: [] },
        ])
      }
    }

    loadChat()

    return () => {
      if (wsRef.current) { try { wsRef.current.close() } catch {} }
      wsRef.current = null
    }
  }, [uploadId, connectChatWs])

  const sendViaWs = (userMsg) => {
    const ws = wsRef.current
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ question: userMsg }))
      return true
    }
    return false
  }

  const sendViaRest = async (userMsg) => {
    try {
      const res = await askChat(uploadId, userMsg)
      setMessages((prev) => [
        ...prev,
        { role: 'ai', text: res.answer, sources: res.sources },
      ])
      setRemaining(res.limit - res.exchange_count)
      setLimit(res.limit)
      if (res.summary) {
        setSummary(res.summary)
      }
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

  const toggleListening = () => {
    if (listening) {
      recognitionRef.current?.stop()
      return
    }
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) return
    const recognition = new SpeechRecognition()
    recognition.lang = 'en-US'
    recognition.interimResults = true
    recognition.continuous = true
    inputBeforeListenRef.current = input
    recognition.onresult = (e) => {
      let interim = ''
      let final = ''
      for (let i = 0; i < e.results.length; i++) {
        const transcript = e.results[i][0].transcript
        if (e.results[i].isFinal) {
          final += transcript
        } else {
          interim += transcript
        }
      }
      if (final) {
        const base = inputBeforeListenRef.current
        const newInput = base ? `${base} ${final}` : final
        setInput(newInput)
        inputBeforeListenRef.current = newInput
        setInterimText('')
      } else {
        setInterimText(interim)
      }
    }
    recognition.onend = () => {
      setListening(false)
      setInterimText('')
    }
    recognition.onerror = () => {
      setListening(false)
      setInterimText('')
    }
    recognitionRef.current = recognition
    recognition.start()
    setListening(true)
  }

  const handleNewSession = async () => {
    if (!uploadId) return
    try {
      await startNewChatSession(uploadId)
      // Move current summary to past summaries
      if (summary) {
        setPastSummaries((prev) => [...prev, { summary, session: prev.length + 1 }])
      }
      setSummary(null)
      setRemaining(limit)
      const doc = uploads.find((u) => u.id === uploadId)
      const name = doc?.filename || 'Document'
      setMessages([{ role: 'ai', text: `Ask me anything about ${name}!`, sources: [] }])
      connectChatWs(uploadId)
    } catch {}
  }

  const send = async () => {
    if (!input.trim() || !uploadId || !qaReady || typing) return
    const userMsg = input.trim()
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', text: userMsg }])
    setTyping(true)

    // Try WebSocket first, fall back to REST
    if (!sendViaWs(userMsg)) {
      await sendViaRest(userMsg)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  const inputDisabled = !uploadId || !qaReady || (remaining !== null && remaining <= 0)
  const used = limit && remaining !== null ? limit - remaining : 0

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 sm:px-6 py-4 border-b border-border bg-surface/50 backdrop-blur-sm">
        <button
          onClick={() => window.history.back()}
          className="sm:hidden flex items-center text-text-muted hover:text-primary cursor-pointer transition-colors"
        >
          <ArrowL />
        </button>
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
        {remaining !== null && limit !== null && (
          <div className="flex flex-col items-end gap-1">
            <span className={`text-xs font-semibold whitespace-nowrap ${
              remaining <= 0 ? 'text-danger' : remaining <= 2 ? 'text-warning' : 'text-text-secondary'
            }`}>
              {remaining > 0 ? `${remaining} of ${limit} left` : 'Completed'}
            </span>
            <div className="w-24 h-1.5 bg-surface-alt rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  remaining <= 0 ? 'bg-danger' : remaining <= 2 ? 'bg-warning' : 'bg-primary'
                }`}
                style={{ width: `${(used / limit) * 100}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 sm:px-6 py-4 sm:py-6 space-y-4">
        {pastSummaries.length > 0 && (
          <div className="space-y-2 mb-2">
            {pastSummaries.map((s, i) => (
              <details key={i} className="bg-surface border border-border rounded-lg">
                <summary className="px-3 py-2 text-xs text-text-muted cursor-pointer hover:text-text-secondary">
                  Session {s.session} Summary
                </summary>
                <p className="px-3 pb-3 text-sm text-text-secondary leading-relaxed whitespace-pre-line">{s.summary}</p>
              </details>
            ))}
          </div>
        )}
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
      <div className="px-4 sm:px-6 py-4 border-t border-border bg-surface/50 backdrop-blur-sm">
        {!qaReady && uploadId && (
          <p className="text-xs text-warning mb-2">Document is still processing. Chat will be available once complete.</p>
        )}
        {remaining !== null && remaining <= 0 && (
          <div className="mb-3">
            {summary ? (
              <div className="bg-surface border border-primary/20 rounded-xl p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Sparkle />
                  <span className="text-sm font-semibold text-primary-light">Conversation Summary</span>
                </div>
                <p className="text-sm text-text-secondary leading-relaxed whitespace-pre-line">
                  {summary}
                </p>
                <button
                  onClick={handleNewSession}
                  className="mt-3 px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors cursor-pointer"
                >
                  Start New Chat
                </button>
              </div>
            ) : (
              <p className="text-xs text-text-muted">
                All {limit} questions used for this document.
              </p>
            )}
          </div>
        )}
        <div className={`flex items-center gap-3 bg-surface-alt rounded-xl px-4 py-2 border border-border ${inputDisabled ? 'opacity-50' : ''}`}>
          <input
            value={listening && interimText ? `${input} ${interimText}`.trim() : input}
            onChange={(e) => { if (!listening) setInput(e.target.value) }}
            onKeyDown={handleKeyDown}
            placeholder={listening ? 'Listening...' : inputDisabled ? 'Chat unavailable' : 'Ask about your document...'}
            disabled={inputDisabled}
            className="flex-1 bg-transparent outline-none text-sm text-text placeholder:text-text-muted/50 disabled:cursor-not-allowed"
          />
          {!inputDisabled && (
            <button
              onClick={toggleListening}
              className={`p-2 rounded-lg transition-all cursor-pointer ${
                listening ? 'bg-danger text-white animate-pulse' : 'text-text-muted hover:text-primary'
              }`}
            >
              {listening ? <MicOff /> : <Mic />}
            </button>
          )}
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
