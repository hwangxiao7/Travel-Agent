import { useI18n } from '../i18n'
import { PREFERENCES, PREF_ICONS, type Preference, type TripType } from '../types'

interface Props {
  originLabel: string
  onOriginLabel: (v: string) => void
  tripType: TripType
  onTripType: (v: TripType) => void
  startDate: string
  onStartDate: (v: string) => void
  maxDriveHours: number
  onMaxDrive: (v: number) => void
  allowFlight: boolean
  onAllowFlight: (v: boolean) => void
  preferences: Preference[]
  onTogglePref: (p: Preference) => void
  query: string
  onQuery: (v: string) => void
  loading: boolean
  onRun: () => void
}

export function PlannerPanel(props: Props) {
  const { t, prefLabel } = useI18n()
  return (
    <section className="sticker cream">
      <h2 className="card-title">🗺️ {t('planner.constraints')}</h2>

      <label className="field">
        {t('planner.home')}
        <input value={props.originLabel} onChange={(e) => props.onOriginLabel(e.target.value)} />
      </label>

      <div className="trip-type-row">
        <button
          type="button"
          className={`pref-chip ${props.tripType === 'day-trip' ? 'on' : ''}`}
          onClick={() => props.onTripType('day-trip')}
        >
          <img src="/icons/icon-daytrip.webp" alt="" />
          {t('planner.day')}
        </button>
        <button
          type="button"
          className={`pref-chip ${props.tripType === 'weekend' ? 'on' : ''}`}
          onClick={() => props.onTripType('weekend')}
        >
          <img src="/icons/icon-weekend.webp" alt="" />
          {t('planner.weekend')}
        </button>
      </div>

      <label className="field">
        {t('planner.start')}
        <input
          type="date"
          value={props.startDate}
          onChange={(e) => props.onStartDate(e.target.value)}
        />
      </label>

      <label className="field">
        {t('planner.drive')}: {props.maxDriveHours.toFixed(1)}h
        <input
          type="range"
          min={0.5}
          max={12}
          step={0.5}
          value={props.maxDriveHours}
          onChange={(e) => props.onMaxDrive(Number(e.target.value))}
        />
      </label>

      <label className="check">
        <input
          type="checkbox"
          checked={props.allowFlight}
          onChange={(e) => props.onAllowFlight(e.target.checked)}
        />
        {t('planner.flight')}
      </label>

      <p className="field-label">{t('planner.prefs')}</p>
      <div className="pref-grid">
        {PREFERENCES.map((p) => (
          <button
            key={p}
            type="button"
            className={`pref-chip ${props.preferences.includes(p) ? 'on' : ''}`}
            onClick={() => props.onTogglePref(p)}
          >
            <img src={PREF_ICONS[p]} alt="" />
            {prefLabel(p)}
          </button>
        ))}
      </div>

      <label className="field">
        {t('planner.search')}
        <input
          value={props.query}
          onChange={(e) => props.onQuery(e.target.value)}
          placeholder={t('planner.searchPh')}
          onKeyDown={(e) => {
            if (e.key === 'Enter') props.onRun()
          }}
        />
      </label>

      <button type="button" className="pill primary" disabled={props.loading} onClick={props.onRun}>
        {t('planner.go')}
      </button>
    </section>
  )
}
