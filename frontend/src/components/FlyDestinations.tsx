import { useI18n } from '../i18n'
import type { FlightsResult, FlyDestination } from '../types'

interface Props {
  destinations: FlyDestination[]
  selectedName: string | null
  loading: boolean
  flightsFor: string | null
  flights: FlightsResult | null
  flightsLoading: boolean
  onSelect: (name: string) => void
  onSearchFlights: (name: string) => void
}

function formatTime(iso: string): string {
  const d = new Date(iso)
  if (isNaN(d.getTime())) return iso
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function FlyDestinations({
  destinations,
  selectedName,
  loading,
  flightsFor,
  flights,
  flightsLoading,
  onSelect,
  onSearchFlights,
}: Props) {
  const { t } = useI18n()
  if (destinations.length === 0) return null

  return (
    <div className="panel fly-panel">
      <h2>✈️ {t('fly.title')}</h2>
      <div className="fly-grid">
        {destinations.map((d) => {
          const active = d.name === selectedName
          const showFlights = flightsFor === d.name
          return (
            <div key={d.name} className={`fly-card ${active ? 'active' : ''}`}>
              <button type="button" className="fly-main" disabled={loading} onClick={() => onSelect(d.name)}>
                <div className="fly-head">
                  <strong>{d.name}</strong>
                  <span className="fly-time">
                    ✈ {d.flight_time} {t('fly.flight')}
                  </span>
                </div>
                <p className="fly-region">
                  {d.region} · {t('fly.from')} {/* origin airport shown via offers */}
                  <span className="fly-airport"> → {d.airport}</span>
                </p>
                <p className="fly-highlight">{d.highlight}</p>
              </button>

              <button
                type="button"
                className="fly-search-btn"
                disabled={flightsLoading}
                onClick={() => onSearchFlights(d.name)}
              >
                {flightsLoading && showFlights ? t('fly.searching') : t('fly.searchFlights')}
              </button>

              {showFlights && flights && (
                <div className="fly-offers">
                  {!flights.has_live_data && <p className="fly-note">{t('fly.noLive')}</p>}
                  {flights.offers.map((o, i) => (
                    <div key={i} className="offer-row">
                      <div className="offer-main">
                        <span className="offer-price">
                          {o.currency} {o.price}
                        </span>
                        <span className="offer-route">
                          {o.depart_airport} → {o.arrive_airport} · {o.duration} ·{' '}
                          {o.stops === 0 ? t('fly.nonstop') : `${o.stops} ${t('fly.stops')}`}
                        </span>
                      </div>
                      <div className="offer-times">
                        {formatTime(o.depart_at)} — {formatTime(o.arrive_at)} · {o.carrier}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
