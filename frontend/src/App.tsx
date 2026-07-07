import { useMemo, useState } from 'react'
import { createPlan, sendChat } from './api/client'
import { ChatPanel } from './components/ChatPanel'
import { ConstraintPanel } from './components/ConstraintPanel'
import { ItineraryCard } from './components/ItineraryCard'
import { MapView } from './components/MapView'
import { useUserPrefs } from './hooks/useUserPrefs'
import { useI18n } from './i18n'
import type { Candidate, ChatMessage, Itinerary } from './types'
import './App.css'

function todayISO() {
  return new Date().toISOString().slice(0, 10)
}

function weekendEndISO(start: string) {
  const d = new Date(start + 'T12:00:00')
  d.setDate(d.getDate() + 1)
  return d.toISOString().slice(0, 10)
}

export default function App() {
  const { t, lang, setLang } = useI18n()
  const { prefs, setPrefs } = useUserPrefs()
  const [tripType, setTripType] = useState<'day-trip' | 'weekend'>('day-trip')
  const [startDate, setStartDate] = useState(todayISO)
  const [endDate, setEndDate] = useState(() => weekendEndISO(todayISO()))
  const [maxDriveHours, setMaxDriveHours] = useState(prefs.defaultMaxDriveHours)
  const [allowFlight, setAllowFlight] = useState(false)
  const [loading, setLoading] = useState(false)
  const [chatLoading, setChatLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [itinerary, setItinerary] = useState<Itinerary | null>(null)
  const [candidates, setCandidates] = useState<Candidate[]>([])
  const [messages, setMessages] = useState<ChatMessage[]>([])

  const selected = useMemo(
    () =>
      itinerary
        ? { lat: itinerary.destination_lat, lng: itinerary.destination_lng, name: itinerary.destination }
        : null,
    [itinerary],
  )

  const handleGenerate = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await createPlan({
        origin: prefs.homeLocation,
        trip_type: tripType,
        start_date: startDate,
        end_date: tripType === 'weekend' ? endDate : null,
        max_drive_hours: maxDriveHours,
        max_flight_hours: prefs.defaultMaxFlightHours,
        preferences: prefs.preferences,
        allow_flight: allowFlight,
        language: lang,
      })
      setItinerary(res.itinerary)
      setCandidates(res.candidates)
      setMessages([
        {
          role: 'assistant',
          content: res.itinerary.summary,
        },
      ])
    } catch (e) {
      setError(e instanceof Error ? e.message : t('app.error'))
    } finally {
      setLoading(false)
    }
  }

  const handleChat = async (text: string) => {
    const nextMessages: ChatMessage[] = [...messages, { role: 'user', content: text }]
    setMessages(nextMessages)
    setChatLoading(true)
    try {
      const res = await sendChat(nextMessages, itinerary, prefs.homeLocation, prefs.preferences, lang)
      setMessages([...nextMessages, { role: 'assistant', content: res.reply }])
      if (res.itinerary) setItinerary(res.itinerary)
    } catch {
      setMessages([...nextMessages, { role: 'assistant', content: t('app.chatError') }])
    } finally {
      setChatLoading(false)
    }
  }

  return (
    <div className="app">
      <header className="topbar">
        <div>
          <h1>{t('app.title')}</h1>
          <p>{t('app.subtitle')}</p>
        </div>
        <div className="lang-switch">
          <button
            type="button"
            className={lang === 'en' ? 'active' : ''}
            onClick={() => setLang('en')}
          >
            EN
          </button>
          <button
            type="button"
            className={lang === 'zh' ? 'active' : ''}
            onClick={() => setLang('zh')}
          >
            中文
          </button>
        </div>
      </header>

      {error && <div className="error-banner">{error}</div>}

      <main className="layout">
        <aside className="sidebar">
          <ConstraintPanel
            prefs={prefs}
            onChange={setPrefs}
            tripType={tripType}
            onTripTypeChange={setTripType}
            startDate={startDate}
            endDate={endDate}
            onStartDateChange={setStartDate}
            onEndDateChange={setEndDate}
            maxDriveHours={maxDriveHours}
            onMaxDriveChange={setMaxDriveHours}
            allowFlight={allowFlight}
            onAllowFlightChange={setAllowFlight}
            loading={loading}
            onGenerate={handleGenerate}
          />
          <ChatPanel
            messages={messages}
            loading={chatLoading}
            onSend={handleChat}
            disabled={!itinerary}
          />
        </aside>

        <section className="main-pane">
          <MapView origin={prefs.homeLocation} candidates={candidates} selected={selected} />
          <ItineraryCard itinerary={itinerary} />
        </section>
      </main>
    </div>
  )
}
