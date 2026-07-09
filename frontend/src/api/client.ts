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

const TOKEN_KEY = 'spontaneous-travel-token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

function authHeaders(): HeadersInit {
  const token = getToken()
  return token
    ? { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }
    : { 'Content-Type': 'application/json' }
}

async function postJson<T>(key: EndpointKey, body: unknown, fallbackError: string): Promise<T> {
  const res = await fetch(apiUrl(key), {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(typeof err.detail === 'string' ? err.detail : fallbackError)
  }
  return res.json()
}

async function getJson<T>(key: EndpointKey, fallbackError: string, query?: Record<string, string>): Promise<T> {
  const res = await fetch(apiUrl(key, query), { headers: authHeaders() })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(typeof err.detail === 'string' ? err.detail : fallbackError)
  }
  return res.json()
}

export interface AuthUser {
  id: number
  email: string
  display_name: string
}

export interface AuthResponse {
  access_token: string
  token_type: string
  user: AuthUser
}

export interface TripOut {
  id: number
  destination: string
  destination_lat: number
  destination_lng: number
  travel_mode: string
  start_date: string
  end_date: string
  summary: string
  places: string[]
  created_at: string
}

export interface ReviewOut {
  id: number
  place_name: string
  destination: string
  rating: number
  comment: string
  author: string
  created_at: string
  updated_at: string
}

export interface PlaceReviewsResponse {
  place_name: string
  average_rating: number
  review_count: number
  reviews: ReviewOut[]
}

export async function register(
  email: string,
  password: string,
  displayName = '',
): Promise<AuthResponse> {
  return postJson('authRegister', { email, password, display_name: displayName }, 'Register failed')
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  return postJson('authLogin', { email, password }, 'Login failed')
}

export async function fetchMe(): Promise<AuthUser> {
  return getJson('authMe', 'Not authenticated')
}

export async function saveTrip(body: {
  destination: string
  destination_lat: number
  destination_lng: number
  travel_mode: 'drive' | 'fly'
  start_date: string
  end_date?: string
  summary: string
  places: string[]
}): Promise<TripOut> {
  return postJson('trips', body, 'Failed to save trip')
}

export async function listTrips(): Promise<TripOut[]> {
  return getJson('tripsList', 'Failed to load trips')
}

export async function upsertReview(body: {
  place_name: string
  destination?: string
  rating: number
  comment: string
}): Promise<ReviewOut> {
  return postJson('reviews', body, 'Failed to save review')
}

export async function fetchPlaceReviews(placeName: string): Promise<PlaceReviewsResponse> {
  const url = `${apiUrl('placeReviews')}/${encodeURIComponent(placeName)}/reviews`
  const r = await fetch(url, { headers: authHeaders() })
  if (!r.ok) {
    const err = await r.json().catch(() => ({}))
    throw new Error(typeof err.detail === 'string' ? err.detail : 'Failed to load reviews')
  }
  return r.json()
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

export interface SearchRequest {
  origin: Location
  query: string
  trip_type: 'day-trip' | 'weekend'
  start_date: string
  end_date?: string | null
  max_drive_hours: number
  max_flight_hours: number
  preferences: Preference[]
  allow_flight: boolean
  language: string
}

export async function searchPlan(
  body: SearchRequest,
): Promise<PlanResponse & { semantic: boolean }> {
  return postJson('search', body, 'Search failed')
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
