import { useEffect, useState } from 'react'
import type { UserPrefs } from '../types'

const STORAGE_KEY = 'spontaneous-travel-prefs'

const DEFAULT_PREFS: UserPrefs = {
  homeLocation: { lat: 37.7749, lng: -122.4194, label: 'San Francisco, CA' },
  preferences: ['national-park', 'hiking'],
  defaultMaxDriveHours: 3,
  defaultMaxFlightHours: 2,
}

export function useUserPrefs() {
  const [prefs, setPrefs] = useState<UserPrefs>(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      return raw ? { ...DEFAULT_PREFS, ...JSON.parse(raw) } : DEFAULT_PREFS
    } catch {
      return DEFAULT_PREFS
    }
  })

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs))
  }, [prefs])

  return { prefs, setPrefs }
}
