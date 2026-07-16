import { useEffect, useState } from 'react'
import {
  fetchMe,
  fetchPersona,
  fetchPersonaQuiz,
  login,
  logout,
  register,
  submitPersonaQuiz,
  myTrips,
  myReviews,
} from '../api/client'
import { useI18n } from '../i18n'
import type { AuthUser, Persona, QuizQuestion } from '../types'

interface Props {
  open: boolean
  onClose: () => void
  user: AuthUser | null
  onUser: (u: AuthUser | null) => void
}

export function AccountModal({ open, onClose, user, onUser }: Props) {
  const { t, lang, setLang } = useI18n()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
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
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed')
    } finally {
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
            </div>
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
            <button type="button" className="pill primary" disabled={busy} onClick={() => void submitAuth()}>
              {mode === 'login' ? t('account.login') : t('account.register')}
            </button>
          </div>
        ) : (
          <div className="account-body">
            <div className="profile-card">
              <img src="/icons/mascot.webp" alt="" className="mascot-sm" />
              <div>
                <strong>{user.display_name || user.email}</strong>
                <p className="muted small">{user.email}</p>
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
                </>
              ) : (
                <p className="muted small">—</p>
              )}
              {!quiz ? (
                <button type="button" className="pill" onClick={() => void startQuiz()} disabled={busy}>
                  {t('account.quiz')}
                </button>
              ) : (
                <div className="quiz">
                  {quiz.map((q) => (
                    <div key={q.id} className="quiz-q">
                      <p>{q.prompt}</p>
                      <div className="chip-row wrap">
                        {q.options.map((o) => (
                          <button
                            key={o.id}
                            type="button"
                            className={`chip soft ${answers[q.id] === o.id ? 'on' : ''}`}
                            onClick={() => setAnswers((a) => ({ ...a, [q.id]: o.id }))}
                          >
                            {o.label}
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                  <button
                    type="button"
                    className="pill primary"
                    disabled={busy || Object.keys(answers).length < quiz.length}
                    onClick={() => void finishQuiz()}
                  >
                    {t('surprise.match')}
                  </button>
                </div>
              )}
            </section>

            <section className="sticker cream nested">
              <h3>{t('account.trips')}</h3>
              {trips.length === 0 && <p className="muted small">—</p>}
              <ul className="simple-list">
                {trips.map((tr) => (
                  <li key={tr.id}>
                    <strong>{tr.destination}</strong>
                    <span className="muted small">{tr.summary}</span>
                  </li>
                ))}
              </ul>
            </section>

            <section className="sticker cream nested">
              <h3>{t('account.reviews')}</h3>
              {reviews.length === 0 && <p className="muted small">—</p>}
              <ul className="simple-list">
                {reviews.map((r, i) => (
                  <li key={`${r.place_name}-${i}`}>
                    <strong>
                      {r.place_name} · {'★'.repeat(Math.round(r.rating))}
                    </strong>
                    <span className="muted small">{r.comment}</span>
                  </li>
                ))}
              </ul>
            </section>

            <section className="sticker cream nested">
              <h3>{t('account.language')}</h3>
              <div className="seg">
                <button type="button" className={lang === 'en' ? 'on' : ''} onClick={() => setLang('en')}>
                  EN
                </button>
                <button type="button" className={lang === 'zh' ? 'on' : ''} onClick={() => setLang('zh')}>
                  中文
                </button>
              </div>
            </section>

            {error && <p className="error-text">{error}</p>}
            <button
              type="button"
              className="pill ghost"
              onClick={() => {
                logout()
                onUser(null)
                setPersona(null)
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
