import { useState } from 'react'
import { useI18n } from '../i18n'
import type { Location, Preference, UserPrefs } from '../types'
import { AddressSearch } from './AddressSearch'

const ALL_PREFS: Preference[] = ['national-park', 'hiking', 'city-walk', 'forest', 'beach']

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
  searchQuery: string
  onSearchQueryChange: (v: string) => void
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
  searchQuery,
  onSearchQueryChange,
}: Props) {
  const { t } = useI18n()
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
      setGeoError(t('panel.geoUnsupported'))
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
            label: t('panel.myLocation'),
          },
        })
        setLocating(false)
      },
      () => {
        setGeoError(t('panel.geoFailed'))
        setLocating(false)
      },
      { enableHighAccuracy: false, timeout: 8000 },
    )
  }

  return (
    <div className="panel constraint-panel">
      <h2>{t('panel.title')}</h2>

      <div className="field">
        <span>{t('panel.homeBase')}</span>
        <AddressSearch
          value={prefs.homeLocation.label}
          onSelect={selectLocation}
          onTextChange={setLabel}
        />
      </div>

      <button type="button" className="ghost" disabled={locating} onClick={useMyLocation}>
        {locating ? t('panel.locating') : t('panel.useLocation')}
      </button>
      {geoError && <p className="geo-error">{geoError}</p>}

      <div className="field">
        <span>{t('panel.tripType')}</span>
        <div className="segmented">
          <button
            type="button"
            className={tripType === 'day-trip' ? 'active' : ''}
            onClick={() => onTripTypeChange('day-trip')}
          >
            {t('panel.dayTrip')}
          </button>
          <button
            type="button"
            className={tripType === 'weekend' ? 'active' : ''}
            onClick={() => onTripTypeChange('weekend')}
          >
            {t('panel.weekend')}
          </button>
        </div>
      </div>

      <label className="field">
        <span>{t('panel.startDate')}</span>
        <input type="date" value={startDate} onChange={(e) => onStartDateChange(e.target.value)} />
      </label>

      {tripType === 'weekend' && (
        <label className="field">
          <span>{t('panel.endDate')}</span>
          <input type="date" value={endDate} onChange={(e) => onEndDateChange(e.target.value)} />
        </label>
      )}

      <label className="field">
        <span>
          {t('panel.maxDrive')}: {maxDriveHours}h
        </span>
        <input
          type="range"
          min={1}
          max={8}
          step={0.5}
          value={maxDriveHours}
          onChange={(e) => onMaxDriveChange(parseFloat(e.target.value))}
        />
      </label>

      <label className="checkbox">
        <input
          type="checkbox"
          checked={allowFlight}
          onChange={(e) => onAllowFlightChange(e.target.checked)}
        />
        {t('panel.includeFlight')}
      </label>

      <div className="field">
        <span>{t('panel.preferences')}</span>
        <div className="tags">
          {ALL_PREFS.map((p) => (
            <button
              key={p}
              type="button"
              className={`tag ${prefs.preferences.includes(p) ? 'active' : ''}`}
              onClick={() => togglePref(p)}
            >
              {t(`pref.${p}`)}
            </button>
          ))}
        </div>
      </div>

      <div className="field search-field">
        <span>{t('panel.search')}</span>
        <textarea
          className="search-input"
          rows={2}
          placeholder={t('panel.searchPlaceholder')}
          value={searchQuery}
          onChange={(e) => onSearchQueryChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) onGenerate()
          }}
        />
      </div>

      <button type="button" className="primary" disabled={loading} onClick={onGenerate}>
        {loading
          ? t('panel.planning')
          : searchQuery.trim()
            ? t('panel.searchBtn')
            : t('panel.generate')}
      </button>
    </div>
  )
}
