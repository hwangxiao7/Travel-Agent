export type Preference =
  | 'national-park'
  | 'hiking'
  | 'city-walk'
  | 'forest'
  | 'beach'

export type TripType = 'day-trip' | 'weekend'
export type Lang = 'en' | 'zh'
export type HomeModule = 'surprise' | 'planner'

export interface Location {
  lat: number
  lng: number
  label: string
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
  packing_tips?: string[]
  weather_note?: string
  summary?: string
  travel_mode?: 'drive' | 'fly'
}

export interface Candidate {
  name: string
  lat: number
  lng: number
  drive_time: string
  drive_hours: number
  highlight: string
  explanation?: string
  travel_mode?: 'drive' | 'fly'
  trip_scope?: 'local' | 'regional' | 'distant' | null
  trip_scope_label?: string
  trip_kind?: 'local_play' | 'away'
  display_group?: 'local' | 'regional' | 'distant' | 'fly'
  semantic_tags?: string[]
  source?: string
}

export interface ActivityIdea {
  key: string
  name: string
  name_en?: string
  name_zh?: string
  tags: string[]
  duration_h: number
  energy: string
  cost: string
  indoor: boolean
  in_season: boolean
  match_score: number
  blurb: string
  reason: string
  /** Shared vibe sticker key (e.g. vibe-water). */
  icon_key?: string
}

export interface ActivityVenue {
  name: string
  lat: number
  lng: number
  distance_miles: number
  drive_time: string
  source: string
  query: string
  blurb: string
}

export interface AuthUser {
  id: number
  email: string
  display_name: string
  contact?: string
  home_label?: string
  home_lat?: number
  home_lng?: number
  default_prefs?: Preference[]
  phone?: string
  has_password?: boolean
  auth_providers?: string[]
}

export interface AuthMethods {
  email: boolean
  phone: boolean
  wechat: boolean
}

export interface PersonaAxis {
  key: string
  label: string
  left: string
  right: string
  score: number
}

export interface Persona {
  title: string
  type_code: string
  blurb: string
  confidence: number
  axes: PersonaAxis[]
  has_quiz: boolean
}

export interface QuizOption {
  id: string
  label: string
}

export interface QuizQuestion {
  id: string
  prompt: string
  options: QuizOption[]
}

export const PREFERENCES: Preference[] = [
  'national-park',
  'hiking',
  'city-walk',
  'forest',
  'beach',
]

export const PREF_ICONS: Record<Preference, string> = {
  'national-park': '/icons/icon-national-park.webp',
  hiking: '/icons/icon-hiking.webp',
  'city-walk': '/icons/icon-city-walk.webp',
  forest: '/icons/icon-forest.webp',
  beach: '/icons/icon-beach.webp',
}

export const SF_DEFAULT: Location = {
  lat: 37.7749,
  lng: -122.4194,
  label: 'San Francisco, CA',
}
