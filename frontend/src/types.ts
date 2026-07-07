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
