import { useState, useRef, useEffect } from 'react'
import { Send, Sparkle } from '../components/Icons'

const AI_RESPONSES = [
  'Based on the document, neural networks were inspired by biological neural networks in the human brain. The perceptron was the first model, created in 1958.',
  'The Transformer architecture uses self-attention to process all tokens in parallel, unlike RNNs which process sequentially. This is covered in pages 5-9 of your document.',
  'Great question! Gradient descent works by computing the gradient of the loss function and updating parameters to minimize it. Adam and SGD are the most popular variants.',
  'CNNs use convolutional layers with learnable filters that detect features like edges and textures. Parameter sharing is the key innovation that reduces model size.',
  'Reinforcement learning involves an agent learning through trial and error, receiving rewards for good actions. The exploration-exploitation trade-off is fundamental to RL.',
]

export default function ChatPage() {
  const [messages, setMessages] = useState([
    { role: 'ai', text: 'Hi! I\'m Verso AI. Ask me anything about your uploaded documents.', sources: [] },
  ])
  const [input, setInput] = useState('')
  const [typing, setTyping] = useState(false)
  const endRef = useRef(null)
  const responseIdx = useRef(0)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, typing])

  const send = () => {
    if (!input.trim()) return
    const userMsg = input.trim()
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', text: userMsg }])
    setTyping(true)

    setTimeout(() => {
      setTyping(false)
      const reply = AI_RESPONSES[responseIdx.current % AI_RESPONSES.length]
      responseIdx.current++
      setMessages((prev) => [
        ...prev,
        { role: 'ai', text: reply, sources: ['Document p.1-4'] },
      ])
    }, 1200 + Math.random() * 800)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <div className="flex items-center gap-3 px-6 py-4 border-b border-border bg-surface/50 backdrop-blur-sm">
        <div className="w-9 h-9 rounded-full bg-primary/10 flex items-center justify-center text-primary">
          <Sparkle />
        </div>
        <div>
          <h2 className="text-sm font-semibold">Ask Verso</h2>
          <p className="text-text-muted text-xs">Deep Learning Fundamentals.pdf</p>
        </div>
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
                  : 'bg-surface border border-border text-text-secondary rounded-bl-md'
              }`}
            >
              {msg.text}
              {msg.sources?.length > 0 && (
                <div className="flex gap-2 mt-2 pt-2 border-t border-border">
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

        {/* Typing indicator */}
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
        <div className="flex items-center gap-3 bg-surface-alt rounded-xl px-4 py-2 border border-border">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about your document..."
            className="flex-1 bg-transparent outline-none text-sm text-text placeholder:text-text-muted/50"
          />
          <button
            onClick={send}
            disabled={!input.trim()}
            className={`p-2 rounded-lg transition-all cursor-pointer ${
              input.trim()
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
