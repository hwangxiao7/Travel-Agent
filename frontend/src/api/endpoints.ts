// Central registry of backend API routes.
// Change a path here (or the base) to reroute the whole app in one place.

export const API_BASE = import.meta.env.VITE_API_BASE ?? ''

export const ENDPOINTS = {
  geocode: '/api/geocode',
  plan: '/api/plan',
  search: '/api/search',
  select: '/api/select',
  chat: '/api/chat',
  flyDestinations: '/api/fly-destinations',
  flyPrices: '/api/fly-prices',
  flyPlan: '/api/fly-plan',
  flights: '/api/flights',
  flightsCalendar: '/api/flights/calendar',
  authRegister: '/api/auth/register',
  authLogin: '/api/auth/login',
  authMe: '/api/auth/me',
  trips: '/api/trips',
  tripsList: '/api/trips',
  reviews: '/api/reviews',
  placeReviews: '/api/places', // append /{name}/reviews in client
} as const

export type EndpointKey = keyof typeof ENDPOINTS

export function apiUrl(key: EndpointKey, query?: Record<string, string>): string {
  let url = `${API_BASE}${ENDPOINTS[key]}`
  if (query && Object.keys(query).length > 0) {
    url += `?${new URLSearchParams(query).toString()}`
  }
  return url
}
