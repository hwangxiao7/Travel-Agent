import { useEffect, useState } from 'react'
import {
  fetchAuthMethods,
  fetchMe,
  fetchPersona,
  fetchPersonaQuiz,
  login,
  logout,
  phoneSend,
  phoneVerify,
  register,
  submitPersonaQuiz,
  myTrips,
  myReviews,
  wechatExchange,
  wechatStart,
} from '../api/client'
import { useI18n } from '../i18n'
import type { AuthMethods, AuthUser, Location, Persona, QuizQuestion } from '../types'
import { InspirationUpload } from './InspirationUpload'

interface Props {
  open: boolean
  onClose: () => void
  user: AuthUser | null
  onUser: (u: AuthUser | null) => void
  origin?: Location
}

export function AccountModal({ open, onClose, user, onUser, origin }: Props) {
  const { t, lang, setLang } = useI18n()
  const [mode, setMode] = useState<'login' | 'register' | 'phone'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [otp, setOtp] = useState('')
  const [methods, setMethods] = useState<AuthMethods>({ email: true, phone: false, wechat: false })
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [persona, setPersona] = useState<Persona | null>(null)
  const [quiz, setQuiz] = useState<QuizQuestion[] | null>(null)
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [trips, setTrips] = useState<Array<{ id: number; destination: string; summary: string }>>([])
  const [reviews, setReviews] = useState<Array<{ place_name: string; rating: number; comment: string }>>(
    [],
  )

  useEffect(() => {
    if (!open) return
    void fetchAuthMethods().then(setMethods)
  }, [open])

  useEffect(() => {
    if (!open || !user) return
    void (async () => {
      try {
        setPersona(await fetchPersona())
        setTrips(await myTrips())
        const r = await myReviews()
        setReviews(r.reviews || [])
      } catch {
        /* anonymous gaps ok */
      }
    })()
  }, [open, user])

  if (!open) return null

  const submitAuth = async () => {
    setBusy(true)
    setError(null)
    try {
      const res =
        mode === 'login'
          ? await login(email, password)
          : await register(email, password, name || email.split('@')[0])
      onUser(res.user)
      const { flushLikes } = await import('../likes')
      await flushLikes()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed')
    } finally {
      setBusy(false)
    }
  }

  const sendOtp = async () => {
    setBusy(true)
    setError(null)
    try {
      await phoneSend(phone)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed')
    } finally {
      setBusy(false)
    }
  }

  const verifyOtp = async () => {
    setBusy(true)
    setError(null)
    try {
      const res = await phoneVerify(phone, otp, name)
      onUser(res.user)
      const { flushLikes } = await import('../likes')
      await flushLikes()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed')
    } finally {
      setBusy(false)
    }
  }

  const startWechat = async () => {
    setBusy(true)
    setError(null)
    try {
      const returnTo = `${window.location.origin}${window.location.pathname}`
      const { authorize_url } = await wechatStart(returnTo)
      window.location.href = authorize_url
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed')
      setBusy(false)
    }
  }

  const startQuiz = async () => {
    setBusy(true)
    try {
      const q = await fetchPersonaQuiz(lang)
      setQuiz(q.questions)
      setAnswers({})
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed')
    } finally {
      setBusy(false)
    }
  }

  const finishQuiz = async () => {
    if (!quiz) return
    setBusy(true)
    try {
      const p = await submitPersonaQuiz(answers)
      setPersona(p)
      setQuiz(null)
      onUser(await fetchMe())
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose} role="presentation">
      <div className="modal sheet" onClick={(e) => e.stopPropagation()} role="dialog">
        <div className="modal-head">
          <h2>{t('account.title')}</h2>
          <button type="button" className="icon-btn" onClick={onClose}>
            ✕
          </button>
        </div>

        {!user ? (
          <div className="auth-form">
            <div className="seg">
              <button
                type="button"
                className={mode === 'login' ? 'on' : ''}
                onClick={() => setMode('login')}
              >
                {t('account.login')}
              </button>
              <button
                type="button"
                className={mode === 'register' ? 'on' : ''}
                onClick={() => setMode('register')}
              >
                {t('account.register')}
              </button>
              {methods.phone && (
                <button
                  type="button"
                  className={mode === 'phone' ? 'on' : ''}
                  onClick={() => setMode('phone')}
                >
                  {lang === 'zh' ? '手机' : 'Phone'}
                </button>
              )}
            </div>

            {mode === 'phone' ? (
              <>
                <label className="field">
                  {lang === 'zh' ? '手机号' : 'Phone'}
                  <input
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="+86 / 11 digits"
                    inputMode="tel"
                  />
                </label>
                <label className="field">
                  {lang === 'zh' ? '验证码' : 'Code'}
                  <input value={otp} onChange={(e) => setOtp(e.target.value)} inputMode="numeric" />
                </label>
                {error && <p className="error-text">{error}</p>}
                <div className="auth-actions">
                  <button type="button" className="pill" disabled={busy || !phone} onClick={() => void sendOtp()}>
                    {lang === 'zh' ? '发送验证码' : 'Send code'}
                  </button>
                  <button
                    type="button"
                    className="pill primary"
                    disabled={busy || !phone || !otp}
                    onClick={() => void verifyOtp()}
                  >
                    {lang === 'zh' ? '登录' : 'Verify & sign in'}
                  </button>
                </div>
              </>
            ) : (
              <>
                {mode === 'register' && (
                  <label className="field">
                    {t('account.name')}
                    <input value={name} onChange={(e) => setName(e.target.value)} />
                  </label>
                )}
                <label className="field">
                  {t('account.email')}
                  <input value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
                </label>
                <label className="field">
                  {t('account.password')}
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                  />
                </label>
                {error && <p className="error-text">{error}</p>}
                <button
                  type="button"
                  className="pill primary"
                  disabled={busy}
                  onClick={() => void submitAuth()}
                >
                  {mode === 'login' ? t('account.login') : t('account.register')}
                </button>
              </>
            )}

            {methods.wechat && (
              <button type="button" className="pill wechat" disabled={busy} onClick={() => void startWechat()}>
                {lang === 'zh' ? '微信登录' : 'Continue with WeChat'}
              </button>
            )}
          </div>
        ) : (
          <div className="account-body">
            <div className="profile-card">
              <img src="/icons/mascot.webp" alt="" className="mascot-sm" />
              <div>
                <strong>{user.display_name || user.email || user.phone || 'User'}</strong>
                <p className="muted small">{user.email || user.phone || (user.auth_providers || []).join(' · ')}</p>
              </div>
            </div>

            <section className="sticker cream nested">
              <h3>{t('account.persona')}</h3>
              {persona ? (
                <>
                  <strong>
                    {persona.title} {persona.type_code ? `· ${persona.type_code}` : ''}
                  </strong>
                  <p className="muted small">{persona.blurb}</p>
                  <ul className="axis-list">
                    {(persona.axes || []).slice(0, 6).map((a) => (
                      <li key={a.key}>
                        <span>
                          {a.left} — {a.right}
                        </span>
                        <div className="axis-bar">
                          <i style={{ width: `${Math.max(8, Math.min(100, a.score))}%` }} />
                        </div>
                      </li>
                    ))}
                  </ul>
                  <button type="button" className="pill" onClick={() => void startQuiz()} disabled={busy}>
                    {t('account.quiz')}
                  </button>
                </>
              ) : (
                <button type="button" className="pill primary" onClick={() => void startQuiz()} disabled={busy}>
                  {t('account.quiz')}
                </button>
              )}
              {quiz && (
                <div className="quiz-box">
                  {quiz.map((q) => (
                    <div key={q.id} className="quiz-q">
                      <p>{q.prompt}</p>
                      <div className="chip-row wrap">
                        {q.options.map((o) => (
                          <button
                            key={o.id}
                            type="button"
                            className={`chip ${answers[q.id] === o.id ? 'on' : ''}`}
                            onClick={() => setAnswers((a) => ({ ...a, [q.id]: o.id }))}
                          >
                            {o.label}
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                  <button type="button" className="pill primary" onClick={() => void finishQuiz()} disabled={busy}>
                    {lang === 'zh' ? '保存' : 'Save'}
                  </button>
                </div>
              )}
            </section>

            <section className="sticker cream nested">
              <h3>{t('account.inspiration')}</h3>
              <InspirationUpload
                loggedIn={!!user}
                origin={origin ?? { lat: 37.7749, lng: -122.4194, label: 'SF' }}
              />
            </section>

            <section className="sticker cream nested">
              <h3>{t('account.trips')}</h3>
              {trips.length === 0 ? (
                <p className="muted small">—</p>
              ) : (
                <ul className="plain-list">
                  {trips.slice(0, 5).map((tr) => (
                    <li key={tr.id}>
                      <strong>{tr.destination}</strong>
                      <p className="muted small">{tr.summary}</p>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="sticker cream nested">
              <h3>{t('account.reviews')}</h3>
              {reviews.length === 0 ? (
                <p className="muted small">—</p>
              ) : (
                <ul className="plain-list">
                  {reviews.slice(0, 5).map((r, i) => (
                    <li key={`${r.place_name}-${i}`}>
                      <strong>
                        {r.place_name} · {r.rating}★
                      </strong>
                      <p className="muted small">{r.comment}</p>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="sticker cream nested">
              <h3>{t('account.language')}</h3>
              <div className="seg">
                <button type="button" className={lang === 'en' ? 'on' : ''} onClick={() => setLang('en')}>
                  English
                </button>
                <button type="button" className={lang === 'zh' ? 'on' : ''} onClick={() => setLang('zh')}>
                  中文
                </button>
              </div>
            </section>

            <button
              type="button"
              className="pill"
              onClick={() => {
                logout()
                onUser(null)
              }}
            >
              {t('account.logout')}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

/** Call once on app boot: redeem ?ticket= from WeChat OAuth redirect. */
export async function redeemWechatTicketFromUrl(
  onUser: (u: AuthUser) => void,
): Promise<boolean> {
  const params = new URLSearchParams(window.location.search)
  const ticket = params.get('ticket')
  if (!ticket) return false
  try {
    const res = await wechatExchange(ticket)
    onUser(res.user)
    params.delete('ticket')
    const next = `${window.location.pathname}${params.toString() ? `?${params}` : ''}${window.location.hash}`
    window.history.replaceState({}, '', next)
    return true
  } catch {
    return false
  }
}
