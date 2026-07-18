import { useRef, useState } from 'react'
import { uploadInspirationScreenshot } from '../api/client'
import { useI18n } from '../i18n'
import type { InspirationCapture, Location } from '../types'

interface Props {
  loggedIn: boolean
  origin: Location
  onNeedLogin?: () => void
  variant?: 'banner' | 'block' | 'compact'
}

export function InspirationUpload({
  loggedIn,
  origin,
  onNeedLogin,
  variant = 'block',
}: Props) {
  const { t, lang } = useI18n()
  const inputRef = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [capture, setCapture] = useState<InspirationCapture | null>(null)

  const openPicker = () => {
    if (!loggedIn) {
      onNeedLogin?.()
      return
    }
    inputRef.current?.click()
  }

  const onFile = async (file: File | undefined) => {
    if (!file) return
    setBusy(true)
    setError(null)
    setCapture(null)
    try {
      const res = await uploadInspirationScreenshot(file, origin, lang)
      setCapture(res.capture)
    } catch (e) {
      setError(e instanceof Error ? e.message : t('inspiration.failed'))
    } finally {
      setBusy(false)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  const resultBlock = capture ? (
    <div className="inspiration-result">
      <strong>{capture.activity_title}</strong>
      {capture.summary && <p className="muted small">{capture.summary}</p>}
      {capture.places.length > 0 && (
        <p className="small">
          {t('inspiration.places')}: {capture.places.map((p) => p.name).join(' · ')}
        </p>
      )}
      {capture.must_bring.length > 0 && (
        <p className="small">
          {t('inspiration.mustBring')}: {capture.must_bring.join(' · ')}
        </p>
      )}
      {capture.must_do_tips.length > 0 && (
        <p className="small">
          {t('inspiration.mustTips')}: {capture.must_do_tips.join(' · ')}
        </p>
      )}
      <p className="muted small ok">{t('inspiration.saved')}</p>
    </div>
  ) : null

  const fileInput = (
    <input
      ref={inputRef}
      type="file"
      accept="image/jpeg,image/png,image/webp"
      hidden
      onChange={(e) => void onFile(e.target.files?.[0])}
    />
  )

  if (variant === 'banner') {
    return (
      <div className="inspiration-banner-wrap">
        {fileInput}
        <button
          type="button"
          className="inspiration-banner"
          onClick={openPicker}
          disabled={busy}
        >
          <span className="inspiration-banner-icon" aria-hidden>
            📸
          </span>
          <span className="inspiration-banner-copy">
            <strong>{t('inspiration.bannerTitle')}</strong>
            <span className="muted small">
              {loggedIn ? t('inspiration.bannerSub') : t('inspiration.loginHint')}
            </span>
          </span>
          <span className="inspiration-banner-action" aria-hidden>
            {busy ? '…' : loggedIn ? '↑' : '+'}
          </span>
        </button>
        {error && <p className="error-text">{error}</p>}
        {resultBlock}
      </div>
    )
  }

  const compact = variant === 'compact'

  return (
    <div className={compact ? 'inspiration-compact' : 'inspiration-block'}>
      {fileInput}
      <button type="button" className={compact ? 'pill' : 'pill primary'} onClick={openPicker} disabled={busy}>
        {busy ? t('inspiration.reading') : t('inspiration.cta')}
      </button>
      {!compact && <p className="muted small">{t('inspiration.note')}</p>}
      {compact && !loggedIn && <p className="muted small">{t('inspiration.loginHint')}</p>}
      {error && <p className="error-text">{error}</p>}
      {resultBlock}
    </div>
  )
}
