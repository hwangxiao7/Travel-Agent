import type { Preference, UserPrefs } from '../types'

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
  const togglePref = (id: Preference) => {
    const set = new Set(prefs.preferences)
    if (set.has(id)) set.delete(id)
    else set.add(id)
    onChange({ ...prefs, preferences: [...set] })
  }

  return (
    <div className="panel constraint-panel">
      <h2>Trip constraints</h2>

      <label className="field">
        <span>Home base</span>
        <input
          value={prefs.homeLocation.label}
          onChange={(e) =>
            onChange({
              ...prefs,
              homeLocation: { ...prefs.homeLocation, label: e.target.value },
            })
          }
          placeholder="City or neighborhood"
        />
      </label>

      <div className="coords-row">
        <label className="field">
          <span>Lat</span>
          <input
            type="number"
            step="0.0001"
            value={prefs.homeLocation.lat}
            onChange={(e) =>
              onChange({
                ...prefs,
                homeLocation: { ...prefs.homeLocation, lat: parseFloat(e.target.value) || 0 },
              })
            }
          />
        </label>
        <label className="field">
          <span>Lng</span>
          <input
            type="number"
            step="0.0001"
            value={prefs.homeLocation.lng}
            onChange={(e) =>
              onChange({
                ...prefs,
                homeLocation: { ...prefs.homeLocation, lng: parseFloat(e.target.value) || 0 },
              })
            }
          />
        </label>
      </div>

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
