export type Preference =
  | 'national-park'
  | 'hiking'
  | 'city-walk'
  | 'forest'
  | 'beach'

export interface Location {
  lat: number
  lng: number
  label: string
}

export interface UserPrefs {
  homeLocation: Location
  preferences: Preference[]
  defaultMaxDriveHours: number
  defaultMaxFlightHours: number
}

export interface PlanRequest {
  origin: Location
  trip_type: 'day-trip' | 'weekend'
  start_date: string
  end_date?: string | null
  max_drive_hours: number
  max_flight_hours: number
  preferences: Preference[]
  allow_flight: boolean
  language: string
}

export interface Activity {
  time: string
  place: string
  duration: string
  note: string
}

export interface DayPlan {
  date: string
  activities: Activity[]
}

export interface Place {
  name: string
  category: string
  kind: 'food' | 'fun'
  lat: number
  lng: number
  note: string
  recommended: boolean
}

export interface EventItem {
  name: string
  date: string
  venue: string
  category: string
  url: string
}

export interface Itinerary {
  destination: string
  destination_lat: number
  destination_lng: number
  drive_time: string
  drive_hours: number
  days: DayPlan[]
  alternatives: string[]
  packing_tips: string[]
  weather_note: string
  summary: string
  travel_mode: 'drive' | 'fly'
  origin_airport: string
  destination_airport: string
  nearby_food: Place[]
  nearby_fun: Place[]
  events: EventItem[]
}

export interface FlyDestination {
  name: string
  lat: number
  lng: number
  region: string
  airport: string
  highlight: string
  flight_time: string
  flight_hours: number
  distance_miles: number
}

export interface FlightOffer {
  price: string
  currency: string
  duration: string
  stops: number
  carrier: string
  depart_airport: string
  depart_at: string
  arrive_airport: string
  arrive_at: string
}

export interface FlightsResult {
  origin_airport: string
  arrival_airport: string
  estimate: { flight_time?: string; distance_miles?: number }
  offers: FlightOffer[]
  has_live_data: boolean
}

export interface PriceSummary {
  starting_price: number
  cheapest_day: string
  currency: string
}

export interface FlyPricesResult {
  origin_airport: string
  prices: Record<string, PriceSummary>
}

export interface CalendarDay {
  day: string
  price: number
  group: string
}

export interface CalendarResult {
  origin_airport: string
  arrival_airport: string
  currency: string
  starting_price: number | null
  cheapest_day: string | null
  days: CalendarDay[]
}

export interface Candidate {
  name: string
  lat: number
  lng: number
  drive_time: string
  drive_hours: number
  score: number
  highlight: string
}

export interface PlanResponse {
  itinerary: Itinerary
  candidates: Candidate[]
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}
