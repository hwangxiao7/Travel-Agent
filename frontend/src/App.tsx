import { useMemo, useState } from 'react'
import {
  createPlan,
  fetchFlightCalendar,
  fetchFlyDestinations,
  fetchFlyPrices,
  planFlyDestination,
  searchFlights,
  searchPlan,
  selectDestination,
  sendChat,
} from './api/client'
import { CandidateList } from './components/CandidateList'
import { ChatPanel } from './components/ChatPanel'
import { ConstraintPanel } from './components/ConstraintPanel'
import { FlyDestinations } from './components/FlyDestinations'
import { ItineraryCard } from './components/ItineraryCard'
import { MapView } from './components/MapView'
import { useUserPrefs } from './hooks/useUserPrefs'
import { useI18n } from './i18n'
import type {
  CalendarResult,
  Candidate,
  ChatMessage,
  FlightsResult,
  FlyDestination,
  Itinerary,
  PriceSummary,
} from './types'
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
  const [flyDestinations, setFlyDestinations] = useState<FlyDestination[]>([])
  const [flyPrices, setFlyPrices] = useState<Record<string, PriceSummary>>({})
  const [flightsFor, setFlightsFor] = useState<string | null>(null)
  const [flights, setFlights] = useState<FlightsResult | null>(null)
  const [flightsLoading, setFlightsLoading] = useState(false)
  const [calendar, setCalendar] = useState<CalendarResult | null>(null)
  const [searchQuery, setSearchQuery] = useState('')

  const selected = useMemo(
    () =>
      itinerary
        ? { lat: itinerary.destination_lat, lng: itinerary.destination_lng, name: itinerary.destination }
        : null,
    [itinerary],
  )

  // Shared: load fly-to destinations + prices whenever flights are allowed.
  const loadFlyDestinations = async () => {
    if (!allowFlight) {
      setFlyDestinations([])
      return
    }
    try {
      const fd = await fetchFlyDestinations(
        prefs.homeLocation,
        prefs.defaultMaxFlightHours,
        prefs.preferences,
      )
      setFlyDestinations(fd.destinations)
      const names = fd.destinations.map((d) => d.name)
      if (names.length > 0) {
        fetchFlyPrices(prefs.homeLocation, names, startDate)
          .then((res) => setFlyPrices(res.prices))
          .catch(() => setFlyPrices({}))
      }
    } catch {
      setFlyDestinations([])
    }
  }

  const resetTripState = (itin: Itinerary) => {
    setItinerary(itin)
    setFlightsFor(null)
    setFlights(null)
    setCalendar(null)
    setFlyPrices({})
    setMessages([{ role: 'assistant', content: itin.summary }])
  }

  // Single planning entry point: free-text query → AI search, otherwise the
  // constraint/preference-based plan. Both honor the flight toggle.
  const handlePlan = async () => {
    setLoading(true)
    setError(null)
    try {
      const useSearch = searchQuery.trim().length > 0
      const body = {
        origin: prefs.homeLocation,
        trip_type: tripType,
        start_date: startDate,
        end_date: tripType === 'weekend' ? endDate : null,
        max_drive_hours: maxDriveHours,
        max_flight_hours: prefs.defaultMaxFlightHours,
        preferences: prefs.preferences,
        allow_flight: allowFlight,
        language: lang,
      }
      const res = useSearch
        ? await searchPlan({ ...body, query: searchQuery })
        : await createPlan(body)
      resetTripState(res.itinerary)
      setCandidates(res.candidates)
      await loadFlyDestinations()
    } catch (e) {
      setError(e instanceof Error ? e.message : t('app.error'))
    } finally {
      setLoading(false)
    }
  }

  const handleSelectFly = async (name: string) => {
    if (loading) return
    setLoading(true)
    setError(null)
    try {
      const res = await planFlyDestination({
        origin: prefs.homeLocation,
        destination_name: name,
        trip_type: 'weekend',
        start_date: startDate,
        end_date: endDate,
        preferences: prefs.preferences,
        language: lang,
      })
      setItinerary(res.itinerary)
    } catch (e) {
      setError(e instanceof Error ? e.message : t('app.error'))
    } finally {
      setLoading(false)
    }
  }

  const handleSearchFlights = async (name: string, date?: string) => {
    const departDate = date ?? startDate
    const isNewDestination = name !== flightsFor
    setFlightsFor(name)
    setFlights(null)
    setFlightsLoading(true)
    if (isNewDestination) {
      setCalendar(null)
      fetchFlightCalendar(prefs.homeLocation, name, departDate)
        .then(setCalendar)
        .catch(() => setCalendar(null))
    }
    try {
      const res = await searchFlights(prefs.homeLocation, name, departDate)
      setFlights(res)
    } catch {
      setFlights(null)
    } finally {
      setFlightsLoading(false)
    }
  }

  const handleSelectCandidate = async (name: string) => {
    if (loading) return
    setLoading(true)
    setError(null)
    try {
      const res = await selectDestination({
        origin: prefs.homeLocation,
        destination_name: name,
        trip_type: tripType,
        start_date: startDate,
        end_date: tripType === 'weekend' ? endDate : null,
        preferences: prefs.preferences,
        language: lang,
      })
      setItinerary(res.itinerary)
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
            onGenerate={handlePlan}
            searchQuery={searchQuery}
            onSearchQueryChange={setSearchQuery}
          />
          <ChatPanel
            messages={messages}
            loading={chatLoading}
            onSend={handleChat}
            disabled={!itinerary}
          />
        </aside>

        <section className="main-pane">
          <MapView
            origin={prefs.homeLocation}
            candidates={candidates}
            selected={selected}
            onSelect={handleSelectCandidate}
            food={itinerary?.nearby_food ?? []}
            fun={itinerary?.nearby_fun ?? []}
            flyDestinations={flyDestinations}
          />
          <CandidateList
            candidates={candidates}
            selectedName={itinerary?.destination ?? null}
            loading={loading}
            onSelect={handleSelectCandidate}
          />
          <FlyDestinations
            destinations={flyDestinations}
            prices={flyPrices}
            selectedName={itinerary?.destination ?? null}
            loading={loading}
            flightsFor={flightsFor}
            flights={flights}
            flightsLoading={flightsLoading}
            calendar={calendar}
            onSelect={handleSelectFly}
            onSearchFlights={handleSearchFlights}
          />
          <ItineraryCard itinerary={itinerary} />
        </section>
      </main>
    </div>
  )
}
