import { useState } from 'react'
import { useI18n } from '../i18n'
import type { ChatMessage } from '../types'

interface Props {
  messages: ChatMessage[]
  loading: boolean
  onSend: (text: string) => void
  disabled: boolean
}

export function ChatPanel({ messages, loading, onSend, disabled }: Props) {
  const { t } = useI18n()
  const [input, setInput] = useState('')

  const submit = () => {
    const text = input.trim()
    if (!text || loading || disabled) return
    onSend(text)
    setInput('')
  }

  return (
    <div className="panel chat-panel">
      <h2>{t('chat.title')}</h2>
      <div className="chat-log">
        {messages.length === 0 && <p className="hint">{t('chat.hint')}</p>}
        {messages.map((m, i) => (
          <div key={i} className={`bubble ${m.role}`}>
            {m.content}
          </div>
        ))}
        {loading && <div className="bubble assistant">{t('chat.thinking')}</div>}
      </div>
      <div className="chat-input-row">
        <input
          value={input}
          disabled={disabled || loading}
          placeholder={disabled ? t('chat.disabled') : t('chat.placeholder')}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && submit()}
        />
        <button type="button" disabled={disabled || loading || !input.trim()} onClick={submit}>
          {t('chat.send')}
        </button>
      </div>
    </div>
  )
}
