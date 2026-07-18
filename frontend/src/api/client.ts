import type {
  ActivityIdea,
  ActivityVenue,
  AuthUser,
  Candidate,
  Itinerary,
  Location,
  Persona,
  Preference,
  QuizQuestion,
  TripType,
} from '../types'
import { API_BASE, ENDPOINTS, apiUrl, assetUrl, type EndpointKey } from './endpoints'

export { assetUrl }

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

async function req<T>(
  method: string,
  key: EndpointKey,
  body?: unknown,
  query?: Record<string, string>,
  fallback = 'Request failed',
): Promise<T> {
  const res = await fetch(apiUrl(key, query), {
    method,
    headers: authHeaders(),
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    const detail = (err as { detail?: string }).detail
    throw new Error(typeof detail === 'string' ? detail : fallback)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

export interface AuthResponse {
  access_token: string
  token_type: string
  user: AuthUser
}

export async function register(email: string, password: string, displayName: string) {
  const res = await req<AuthResponse>('POST', 'authRegister', {
    email,
    password,
    display_name: displayName,
  }, undefined, 'Register failed')
  setToken(res.access_token)
  return res
}

export async function login(email: string, password: string) {
  const res = await req<AuthResponse>('POST', 'authLogin', { email, password }, undefined, 'Login failed')
  setToken(res.access_token)
  return res
}

export async function fetchAuthMethods() {
  try {
    return await req<import('../types').AuthMethods>(
      'GET',
      'authMethods',
      undefined,
      undefined,
      'methods',
    )
  } catch {
    return { email: true, phone: false, wechat: false }
  }
}

export async function phoneSend(phone: string) {
  return req<{ ok: boolean; expires_in: number }>(
    'POST',
    'authPhoneSend',
    { phone },
    undefined,
    'Send code failed',
  )
}

export async function phoneVerify(phone: string, code: string, displayName = '') {
  const res = await req<AuthResponse>(
    'POST',
    'authPhoneVerify',
    { phone, code, display_name: displayName },
    undefined,
    'Verify failed',
  )
  setToken(res.access_token)
  return res
}

export async function wechatStart(returnTo: string) {
  return req<{ authorize_url: string }>(
    'GET',
    'authWechatStart',
    undefined,
    { return_to: returnTo },
    'WeChat start failed',
  )
}

export async function wechatExchange(ticket: string) {
  const res = await req<AuthResponse>(
    'POST',
    'authWechatExchange',
    { ticket },
    undefined,
    'WeChat exchange failed',
  )
  setToken(res.access_token)
  return res
}

export async function fetchMe() {
  return req<AuthUser>('GET', 'authMe', undefined, undefined, 'Not signed in')
}

export function logout() {
  setToken(null)
}

export async function fetchActivities(body: {
  interests?: string
  companion?: string
  energy?: string
  language?: string
  k?: number
}) {
  return req<{ activities: ActivityIdea[] }>('POST', 'activities', {
    interests: body.interests ?? '',
    companion: body.companion ?? '',
    energy: body.energy ?? '',
    budget: '',
    weather: '',
    language: body.language ?? 'en',
    k: body.k ?? 8,
  }, undefined, 'Failed to load activities')
}

export async function fetchActivityVenues(body: {
  activity_key: string
  origin: Location
  language?: string
}) {
  return req<{ activity_key: string; activity_name: string; venues: ActivityVenue[] }>(
    'POST',
    'activityVenues',
    {
      activity_key: body.activity_key,
      origin: body.origin,
      radius_miles: 40,
      k: 6,
      language: body.language ?? 'en',
    },
    undefined,
    'Failed to find nearby places',
  )
}

export async function createPlan(body: {
  origin: Location
  trip_type: TripType
  start_date: string
  end_date?: string | null
  max_drive_hours: number
  max_flight_hours?: number
  preferences: Preference[]
  allow_flight: boolean
  language: string
}) {
  return req<{ itinerary: Itinerary; candidates: Candidate[] }>(
    'POST',
    'plan',
    {
      ...body,
      max_flight_hours: body.max_flight_hours ?? 4,
      end_date: body.end_date ?? null,
    },
    undefined,
    'Failed to create plan',
  )
}

export async function searchPlan(body: {
  origin: Location
  query: string
  trip_type: TripType
  start_date: string
  end_date?: string | null
  max_drive_hours: number
  max_flight_hours?: number
  preferences: Preference[]
  allow_flight: boolean
  language: string
}) {
  return req<{ itinerary: Itinerary; candidates: Candidate[]; search_path?: string }>(
    'POST',
    'search',
    {
      ...body,
      max_flight_hours: body.max_flight_hours ?? 4,
      end_date: body.end_date ?? null,
    },
    undefined,
    'Search failed',
  )
}

export async function selectDestination(body: {
  origin: Location
  destination_name: string
  trip_type: TripType
  start_date: string
  end_date?: string | null
  preferences: Preference[]
  language: string
}) {
  return req<{ itinerary: Itinerary }>(
    'POST',
    'select',
    { ...body, end_date: body.end_date ?? null },
    undefined,
    'Failed to load itinerary',
  )
}

export async function fetchPersona() {
  return req<Persona>('GET', 'persona', undefined, undefined, 'Failed to load persona')
}

export async function fetchPersonaQuiz(language: string) {
  return req<{ questions: QuizQuestion[] }>(
    'GET',
    'personaQuiz',
    undefined,
    { language },
    'Failed to load quiz',
  )
}

export async function submitPersonaQuiz(answers: Record<string, string>) {
  return req<Persona>('POST', 'personaQuiz', { answers }, undefined, 'Quiz submit failed')
}

export async function updatePersonaScores(scores: Record<string, number>) {
  return req<Persona>('PATCH', 'persona', { scores }, undefined, 'Failed to update persona')
}

export async function updateProfile(body: {
  display_name?: string
  contact?: string
  home_label?: string
  home_lat?: number
  home_lng?: number
  default_prefs?: Preference[]
}) {
  return req<AuthUser>('PATCH', 'me', body, undefined, 'Failed to update profile')
}

export async function myTrips() {
  return req<
    Array<{
      id: number
      destination: string
      travel_mode: string
      start_date: string
      summary: string
    }>
  >('GET', 'trips', undefined, undefined, 'Failed to load trips')
}

export async function myReviews() {
  return req<{ reviews: Array<{ place_name: string; rating: number; comment: string }> }>(
    'GET',
    'myReviews',
    undefined,
    undefined,
    'Failed to load reviews',
  )
}

export async function sendBetaFeedback(body: {
  rating: number
  note: string
  query?: string
  destination?: string
}) {
  return req<{ ok: boolean }>('POST', 'betaFeedback', { ...body, page: 'web' })
}

export async function uploadInspirationScreenshot(
  file: File,
  origin: Location,
  language: string,
) {
  const token = getToken()
  if (!token) throw new Error('Log in required')

  const form = new FormData()
  form.append('image', file)
  form.append('language', language)
  form.append('origin_lat', String(origin.lat))
  form.append('origin_lng', String(origin.lng))

  const res = await fetch(`${API_BASE}${ENDPOINTS.inspirationScreenshot}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    const detail = (err as { detail?: string }).detail
    throw new Error(typeof detail === 'string' ? detail : 'Upload failed')
  }
  return res.json() as Promise<{ ok: boolean; capture: import('../types').InspirationCapture }>
}
