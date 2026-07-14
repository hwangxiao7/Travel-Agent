import { useState } from 'react'
import { sendBetaFeedback } from '../api/client'
import { useI18n } from '../i18n'

interface Props {
  query?: string
  destination?: string
}

export function BetaFeedback({ query = '', destination = '' }: Props) {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)
  const [rating, setRating] = useState(4)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async () => {
    setBusy(true)
    setError(null)
    try {
      await sendBetaFeedback({ rating, note, query, destination })
      setDone(true)
      setNote('')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="beta-feedback">
      {!open ? (
        <button type="button" className="beta-fab" onClick={() => setOpen(true)}>
          {t('beta.fab')}
        </button>
      ) : (
        <div className="beta-panel">
          <div className="beta-head">
            <strong>{t('beta.title')}</strong>
            <button type="button" className="icon-btn" onClick={() => setOpen(false)}>
              ✕
            </button>
          </div>
          {done ? (
            <p>{t('beta.thanks')}</p>
          ) : (
            <>
              <p className="muted small">{t('beta.hint')}</p>
              <div className="stars">
                {[1, 2, 3, 4, 5].map((n) => (
                  <button
                    key={n}
                    type="button"
                    className={n <= rating ? 'on' : ''}
                    onClick={() => setRating(n)}
                  >
                    ★
                  </button>
                ))}
              </div>
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder={t('beta.placeholder')}
                rows={3}
              />
              {error && <p className="error-text">{error}</p>}
              <button type="button" className="pill primary" disabled={busy} onClick={() => void submit()}>
                {busy ? t('beta.sending') : t('beta.send')}
              </button>
            </>
          )}
        </div>
      )}
    </div>
  )
}
