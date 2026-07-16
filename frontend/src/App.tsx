import { useCallback, useEffect, useState } from 'react'
import {
  createPlan,
  fetchMe,
  getToken,
  searchPlan,
  selectDestination,
} from './api/client'
import { AccountModal } from './components/AccountModal'
import { BetaFeedback } from './components/BetaFeedback'
import { CandidatesAccordion } from './components/CandidatesAccordion'
import { ModeSwitcher } from './components/ModeSwitcher'
import { PlannerPanel } from './components/PlannerPanel'
import { SurprisePanel } from './components/SurprisePanel'
import { useI18n } from './i18n'
import type {
  AuthUser,
  Candidate,
  HomeModule,
  Itinerary,
  Preference,
  TripType,
} from './types'
import { SF_DEFAULT } from './types'
import './App.css'

function todayISO() {
  return new Date().toISOString().slice(0, 10)
}

export default function App() {
  const { t, lang } = useI18n()
  const [module, setModule] = useState<HomeModule>('surprise')
  const [showAccount, setShowAccount] = useState(false)
  const [user, setUser] = useState<AuthUser | null>(null)

  const [originLabel, setOriginLabel] = useState(SF_DEFAULT.label)
  const [origin] = useState(SF_DEFAULT)
  const [tripType, setTripType] = useState<TripType>('day-trip')
  const [startDate, setStartDate] = useState(todayISO)
  const [maxDriveHours, setMaxDriveHours] = useState(3)
  const [allowFlight, setAllowFlight] = useState(false)
  const [preferences, setPreferences] = useState<Preference[]>([])
  const [query, setQuery] = useState('')

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [candidates, setCandidates] = useState<Candidate[]>([])
  const [searchPath, setSearchPath] = useState<string | null>(null)
  const [expandedName, setExpandedName] = useState<string | null>(null)
  const [itineraries, setItineraries] = useState<Record<string, Itinerary>>({})
  const [detailLoading, setDetailLoading] = useState<string | null>(null)

  useEffect(() => {
    void (async () => {
      const { redeemWechatTicketFromUrl } = await import('./components/AccountModal')
      const ok = await redeemWechatTicketFromUrl(setUser)
      if (ok) return
      if (!getToken()) return
      try {
        setUser(await fetchMe())
      } catch {
        setUser(null)
      }
    })()
  }, [])

  useEffect(() => {
    if (user?.default_prefs?.length && preferences.length === 0) {
      setPreferences(user.default_prefs)
    }
  }, [user, preferences.length])

  const togglePref = (p: Preference) => {
    setPreferences((prev) => (prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p]))
  }

  const run = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const base = {
        origin: { ...origin, label: originLabel || origin.label },
        trip_type: tripType,
        start_date: startDate,
        end_date: tripType === 'weekend' ? undefined : null,
        max_drive_hours: maxDriveHours,
        preferences,
        allow_flight: allowFlight,
        language: lang,
      }
      if (query.trim()) {
        const res = await searchPlan({ ...base, query: query.trim() })
        setCandidates(res.candidates)
        setSearchPath(res.search_path ?? 'corpus')
        setItineraries({ [res.itinerary.destination]: res.itinerary })
        setExpandedName(res.itinerary.destination)
      } else {
        const res = await createPlan(base)
        setCandidates(res.candidates)
        setSearchPath(null)
        setItineraries({ [res.itinerary.destination]: res.itinerary })
        setExpandedName(res.itinerary.destination)
      }
      requestAnimationFrame(() => {
        document.getElementById('results')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      })
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed')
      setCandidates([])
    } finally {
      setLoading(false)
    }
  }, [
    allowFlight,
    lang,
    maxDriveHours,
    origin,
    originLabel,
    preferences,
    query,
    startDate,
    tripType,
  ])

  const toggleExpand = async (c: Candidate) => {
    if (expandedName === c.name) {
      setExpandedName(null)
      return
    }
    setExpandedName(c.name)
    if (itineraries[c.name]) return
    setDetailLoading(c.name)
    try {
      const res = await selectDestination({
        origin: { ...origin, label: originLabel || origin.label },
        destination_name: c.name,
        trip_type: tripType,
        start_date: startDate,
        preferences,
        language: lang,
      })
      setItineraries((m) => ({ ...m, [c.name]: res.itinerary }))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed')
    } finally {
      setDetailLoading(null)
    }
  }

  return (
    <div className="app paper">
      <header className="topbar">
        <div>
          <h1>{t('app.title')}</h1>
          <p>{t('app.subtitle')}</p>
        </div>
        <button
          type="button"
          className="mascot-btn"
          onClick={() => setShowAccount(true)}
          aria-label={t('account.title')}
        >
          <img src="/icons/mascot.webp" alt="" />
          <span className={`badge ${user ? 'ok' : 'plus'}`}>{user ? '✓' : '+'}</span>
        </button>
      </header>

      <p className="beta-banner">{t('beta.banner')}</p>

      <main className="home">
        <ModeSwitcher module={module} onChange={setModule} />

        {module === 'surprise' ? (
          <SurprisePanel origin={{ ...origin, label: originLabel || origin.label }} />
        ) : (
          <>
            <PlannerPanel
              originLabel={originLabel}
              onOriginLabel={setOriginLabel}
              tripType={tripType}
              onTripType={setTripType}
              startDate={startDate}
              onStartDate={setStartDate}
              maxDriveHours={maxDriveHours}
              onMaxDrive={setMaxDriveHours}
              allowFlight={allowFlight}
              onAllowFlight={setAllowFlight}
              preferences={preferences}
              onTogglePref={togglePref}
              query={query}
              onQuery={setQuery}
              loading={loading}
              onRun={() => void run()}
            />
            {error && <div className="error-card">{error}</div>}
            <CandidatesAccordion
              candidates={candidates}
              expandedName={expandedName}
              itineraries={itineraries}
              detailLoading={detailLoading}
              searchPath={searchPath}
              onToggle={(c) => void toggleExpand(c)}
            />
          </>
        )}
      </main>

      {loading && (
        <div className="loading-overlay">
          <div className="loading-card">
            <img src="/icons/mascot.webp" alt="" className="bounce" />
            <strong>{t('load.title')}</strong>
            <span className="muted">{t('load.sub')}</span>
          </div>
        </div>
      )}

      <AccountModal
        open={showAccount}
        onClose={() => setShowAccount(false)}
        user={user}
        onUser={setUser}
      />

      <BetaFeedback
        query={query}
        destination={expandedName ? itineraries[expandedName]?.destination ?? expandedName : ''}
      />
    </div>
  )
}
