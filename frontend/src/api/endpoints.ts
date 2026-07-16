// Central registry of backend API routes (same surface as iOS APIClient).

export const API_BASE = import.meta.env.VITE_API_BASE ?? ''

export const ENDPOINTS = {
  geocode: '/api/geocode',
  plan: '/api/plan',
  search: '/api/search',
  select: '/api/select',
  activities: '/api/activities',
  activityVenues: '/api/activities/venues',
  authRegister: '/api/auth/register',
  authLogin: '/api/auth/login',
  authMe: '/api/auth/me',
  me: '/api/me',
  changePassword: '/api/auth/change-password',
  trips: '/api/trips',
  myReviews: '/api/me/reviews',
  persona: '/api/me/persona',
  personaQuiz: '/api/me/persona/quiz',
  betaFeedback: '/api/beta/feedback',
} as const

export type EndpointKey = keyof typeof ENDPOINTS

export function apiUrl(key: EndpointKey, query?: Record<string, string>): string {
  let url = `${API_BASE}${ENDPOINTS[key]}`
  if (query && Object.keys(query).length > 0) {
    url += `?${new URLSearchParams(query).toString()}`
  }
  return url
}

/** Server asset by key — used when a local /icons/{key}.webp is missing. */
export function assetUrl(key: string): string {
  const k = key.trim().replace(/_/g, '-')
  return `${API_BASE}/api/assets/${encodeURIComponent(k)}`
}
