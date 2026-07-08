import type {
  CalendarResult,
  ChatMessage,
  FlightsResult,
  FlyDestination,
  FlyPricesResult,
  Itinerary,
  Location,
  PlanRequest,
  PlanResponse,
  Preference,
} from '../types'

export async function fetchFlyPrices(
  origin: Location,
  destinations: string[],
  departDate: string,
): Promise<FlyPricesResult> {
  const res = await fetch('/api/fly-prices', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ origin, destinations, depart_date: departDate }),
  })
  if (!res.ok) throw new Error('Failed to load fly prices')
  return res.json()
}

export async function fetchFlightCalendar(
  origin: Location,
  destinationName: string,
  departDate: string,
): Promise<CalendarResult> {
  const res = await fetch('/api/flights/calendar', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ origin, destination_name: destinationName, depart_date: departDate }),
  })
  if (!res.ok) throw new Error('Failed to load flight calendar')
  return res.json()
}

export async function fetchFlyDestinations(
  origin: Location,
  maxFlightHours: number,
  preferences: Preference[],
): Promise<{ origin_airport: string; destinations: FlyDestination[] }> {
  const res = await fetch('/api/fly-destinations', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ origin, max_flight_hours: maxFlightHours, preferences }),
  })
  if (!res.ok) throw new Error('Failed to load fly destinations')
  return res.json()
}

export async function planFlyDestination(body: {
  origin: Location
  destination_name: string
  trip_type: 'day-trip' | 'weekend'
  start_date: string
  end_date?: string | null
  preferences: Preference[]
  language: string
}): Promise<{ itinerary: Itinerary }> {
  const res = await fetch('/api/fly-plan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to plan fly trip')
  }
  return res.json()
}

export async function searchFlights(
  origin: Location,
  destinationName: string,
  departureDate: string,
): Promise<FlightsResult> {
  const res = await fetch('/api/flights', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ origin, destination_name: destinationName, departure_date: departureDate }),
  })
  if (!res.ok) throw new Error('Flight search failed')
  return res.json()
}

export interface SelectRequest {
  origin: { lat: number; lng: number; label: string }
  destination_name: string
  trip_type: 'day-trip' | 'weekend'
  start_date: string
  end_date?: string | null
  preferences: Preference[]
  language: string
}

export async function selectDestination(body: SelectRequest): Promise<{ itinerary: Itinerary }> {
  const res = await fetch('/api/select', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to select destination')
  }
  return res.json()
}

export async function createPlan(body: PlanRequest): Promise<PlanResponse> {
  const res = await fetch('/api/plan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to generate plan')
  }
  return res.json()
}

export async function sendChat(
  messages: ChatMessage[],
  currentItinerary: Itinerary | null,
  origin: { lat: number; lng: number; label: string } | null,
  preferences: Preference[],
  language: string,
): Promise<{ reply: string; itinerary: Itinerary | null }> {
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      messages,
      current_itinerary: currentItinerary,
      origin,
      preferences,
      language,
    }),
  })
  if (!res.ok) throw new Error('Chat request failed')
  return res.json()
}
