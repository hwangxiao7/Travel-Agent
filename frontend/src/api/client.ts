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
import { apiUrl, type EndpointKey } from './endpoints'

async function postJson<T>(key: EndpointKey, body: unknown, fallbackError: string): Promise<T> {
  const res = await fetch(apiUrl(key), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || fallbackError)
  }
  return res.json()
}

export async function fetchFlyPrices(
  origin: Location,
  destinations: string[],
  departDate: string,
): Promise<FlyPricesResult> {
  return postJson('flyPrices', { origin, destinations, depart_date: departDate }, 'Failed to load fly prices')
}

export async function fetchFlightCalendar(
  origin: Location,
  destinationName: string,
  departDate: string,
): Promise<CalendarResult> {
  return postJson(
    'flightsCalendar',
    { origin, destination_name: destinationName, depart_date: departDate },
    'Failed to load flight calendar',
  )
}

export async function fetchFlyDestinations(
  origin: Location,
  maxFlightHours: number,
  preferences: Preference[],
): Promise<{ origin_airport: string; destinations: FlyDestination[] }> {
  return postJson(
    'flyDestinations',
    { origin, max_flight_hours: maxFlightHours, preferences },
    'Failed to load fly destinations',
  )
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
  return postJson('flyPlan', body, 'Failed to plan fly trip')
}

export async function searchFlights(
  origin: Location,
  destinationName: string,
  departureDate: string,
): Promise<FlightsResult> {
  return postJson(
    'flights',
    { origin, destination_name: destinationName, departure_date: departureDate },
    'Flight search failed',
  )
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
  return postJson('select', body, 'Failed to select destination')
}

export async function createPlan(body: PlanRequest): Promise<PlanResponse> {
  return postJson('plan', body, 'Failed to generate plan')
}

export async function sendChat(
  messages: ChatMessage[],
  currentItinerary: Itinerary | null,
  origin: { lat: number; lng: number; label: string } | null,
  preferences: Preference[],
  language: string,
): Promise<{ reply: string; itinerary: Itinerary | null }> {
  return postJson(
    'chat',
    {
      messages,
      current_itinerary: currentItinerary,
      origin,
      preferences,
      language,
    },
    'Chat request failed',
  )
}
