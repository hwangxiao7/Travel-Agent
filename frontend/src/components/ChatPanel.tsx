import { useState } from 'react'
import type { ChatMessage } from '../types'

interface Props {
  messages: ChatMessage[]
  loading: boolean
  onSend: (text: string) => void
  disabled: boolean
}

export function ChatPanel({ messages, loading, onSend, disabled }: Props) {
  const [input, setInput] = useState('')

  const submit = () => {
    const text = input.trim()
    if (!text || loading || disabled) return
    onSend(text)
    setInput('')
  }

  return (
    <div className="panel chat-panel">
      <h2>Refine with AI</h2>
      <div className="chat-log">
        {messages.length === 0 && (
          <p className="hint">Try: “Make it more relaxed” or “Suggest something closer”</p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`bubble ${m.role}`}>
            {m.content}
          </div>
        ))}
        {loading && <div className="bubble assistant">Thinking…</div>}
      </div>
      <div className="chat-input-row">
        <input
          value={input}
          disabled={disabled || loading}
          placeholder={disabled ? 'Generate a plan first' : 'Ask to adjust the trip…'}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && submit()}
        />
        <button type="button" disabled={disabled || loading || !input.trim()} onClick={submit}>
          Send
        </button>
      </div>
    </div>
  )
}
