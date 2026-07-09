import { useEffect, useState } from 'react'
import {
  fetchMe,
  getToken,
  login,
  register,
  setToken,
  type AuthUser,
} from '../api/client'
import { useI18n } from '../i18n'

interface Props {
  user: AuthUser | null
  onUserChange: (u: AuthUser | null) => void
}

export function AuthPanel({ user, onUserChange }: Props) {
  const { t } = useI18n()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    const token = getToken()
    if (!token || user) return
    fetchMe()
      .then(onUserChange)
      .catch(() => setToken(null))
  }, [user, onUserChange])

  const submit = async () => {
    setBusy(true)
    setError(null)
    try {
      const res =
        mode === 'login'
          ? await login(email.trim(), password)
          : await register(email.trim(), password, displayName.trim())
      setToken(res.access_token)
      onUserChange(res.user)
      setPassword('')
    } catch (e) {
      setError(e instanceof Error ? e.message : t('auth.failed'))
    } finally {
      setBusy(false)
    }
  }

  const logout = () => {
    setToken(null)
    onUserChange(null)
  }

  if (user) {
    return (
      <div className="panel auth-panel">
        <div className="auth-row">
          <strong>{user.display_name || user.email}</strong>
          <button type="button" className="ghost" onClick={logout}>
            {t('auth.logout')}
          </button>
        </div>
        <p className="auth-hint">{t('auth.loggedInHint')}</p>
      </div>
    )
  }

  return (
    <div className="panel auth-panel">
      <h3>{mode === 'login' ? t('auth.login') : t('auth.register')}</h3>
      <div className="auth-tabs">
        <button
          type="button"
          className={mode === 'login' ? 'active' : ''}
          onClick={() => setMode('login')}
        >
          {t('auth.login')}
        </button>
        <button
          type="button"
          className={mode === 'register' ? 'active' : ''}
          onClick={() => setMode('register')}
        >
          {t('auth.register')}
        </button>
      </div>
      {mode === 'register' && (
        <label className="field">
          <span>{t('auth.name')}</span>
          <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
        </label>
      )}
      <label className="field">
        <span>{t('auth.email')}</span>
        <input
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
      </label>
      <label className="field">
        <span>{t('auth.password')}</span>
        <input
          type="password"
          autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </label>
      {error && <p className="auth-error">{error}</p>}
      <button type="button" className="primary" disabled={busy || !email || !password} onClick={submit}>
        {busy ? t('auth.working') : mode === 'login' ? t('auth.login') : t('auth.register')}
      </button>
    </div>
  )
}
