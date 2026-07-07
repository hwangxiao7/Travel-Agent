import { useState } from 'react'
import type { Location, Preference, UserPrefs } from '../types'
import { AddressSearch } from './AddressSearch'

const ALL_PREFS: { id: Preference; label: string }[] = [
  { id: 'national-park', label: 'National Park' },
  { id: 'hiking', label: 'Hiking' },
  { id: 'city-walk', label: 'City Walk' },
  { id: 'forest', label: 'Forest' },
  { id: 'beach', label: 'Beach' },
]

interface Props {
  prefs: UserPrefs
  onChange: (prefs: UserPrefs) => void
  tripType: 'day-trip' | 'weekend'
  onTripTypeChange: (t: 'day-trip' | 'weekend') => void
  startDate: string
  endDate: string
  onStartDateChange: (v: string) => void
  onEndDateChange: (v: string) => void
  maxDriveHours: number
  onMaxDriveChange: (v: number) => void
  allowFlight: boolean
  onAllowFlightChange: (v: boolean) => void
  loading: boolean
  onGenerate: () => void
}

export function ConstraintPanel({
  prefs,
  onChange,
  tripType,
  onTripTypeChange,
  startDate,
  endDate,
  onStartDateChange,
  onEndDateChange,
  maxDriveHours,
  onMaxDriveChange,
  allowFlight,
  onAllowFlightChange,
  loading,
  onGenerate,
}: Props) {
  const [locating, setLocating] = useState(false)
  const [geoError, setGeoError] = useState<string | null>(null)

  const togglePref = (id: Preference) => {
    const set = new Set(prefs.preferences)
    if (set.has(id)) set.delete(id)
    else set.add(id)
    onChange({ ...prefs, preferences: [...set] })
  }

  const selectLocation = (loc: Location) => {
    onChange({ ...prefs, homeLocation: loc })
  }

  const setLabel = (label: string) => {
    onChange({ ...prefs, homeLocation: { ...prefs.homeLocation, label } })
  }

  const useMyLocation = () => {
    if (!('geolocation' in navigator)) {
      setGeoError('Geolocation not supported in this browser.')
      return
    }
    setLocating(true)
    setGeoError(null)
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        onChange({
          ...prefs,
          homeLocation: {
            lat: Number(pos.coords.latitude.toFixed(4)),
            lng: Number(pos.coords.longitude.toFixed(4)),
            label: 'My current location',
          },
        })
        setLocating(false)
      },
      () => {
        setGeoError('Could not get your location — pick a city instead.')
        setLocating(false)
      },
      { enableHighAccuracy: false, timeout: 8000 },
    )
  }

  return (
    <div className="panel constraint-panel">
      <h2>Trip constraints</h2>

      <div className="field">
        <span>Home base</span>
        <AddressSearch
          value={prefs.homeLocation.label}
          onSelect={selectLocation}
          onTextChange={setLabel}
        />
      </div>

      <button type="button" className="ghost" disabled={locating} onClick={useMyLocation}>
        {locating ? 'Locating…' : '📍 Use my current location'}
      </button>
      {geoError && <p className="geo-error">{geoError}</p>}

      <div className="field">
        <span>Trip type</span>
        <div className="segmented">
          <button
            type="button"
            className={tripType === 'day-trip' ? 'active' : ''}
            onClick={() => onTripTypeChange('day-trip')}
          >
            Day trip
          </button>
          <button
            type="button"
            className={tripType === 'weekend' ? 'active' : ''}
            onClick={() => onTripTypeChange('weekend')}
          >
            Weekend
          </button>
        </div>
      </div>

      <label className="field">
        <span>Start date</span>
        <input type="date" value={startDate} onChange={(e) => onStartDateChange(e.target.value)} />
      </label>

      {tripType === 'weekend' && (
        <label className="field">
          <span>End date</span>
          <input type="date" value={endDate} onChange={(e) => onEndDateChange(e.target.value)} />
        </label>
      )}

      <label className="field">
        <span>Max drive time: {maxDriveHours}h</span>
        <input
          type="range"
          min={1}
          max={8}
          step={0.5}
          value={maxDriveHours}
          onChange={(e) => onMaxDriveChange(parseFloat(e.target.value))}
        />
      </label>

      {tripType === 'weekend' && (
        <label className="checkbox">
          <input
            type="checkbox"
            checked={allowFlight}
            onChange={(e) => onAllowFlightChange(e.target.checked)}
          />
          Include flight-range destinations
        </label>
      )}

      <div className="field">
        <span>Preferences</span>
        <div className="tags">
          {ALL_PREFS.map((p) => (
            <button
              key={p.id}
              type="button"
              className={`tag ${prefs.preferences.includes(p.id) ? 'active' : ''}`}
              onClick={() => togglePref(p.id)}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      <button type="button" className="primary" disabled={loading} onClick={onGenerate}>
        {loading ? 'Planning…' : 'Generate plan'}
      </button>
    </div>
  )
}
