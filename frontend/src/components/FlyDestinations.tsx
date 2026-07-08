import { useMemo } from 'react'
import { useI18n } from '../i18n'
import type { CalendarResult, FlightsResult, FlyDestination, PriceSummary } from '../types'

interface Props {
  destinations: FlyDestination[]
  prices: Record<string, PriceSummary>
  selectedName: string | null
  loading: boolean
  flightsFor: string | null
  flights: FlightsResult | null
  flightsLoading: boolean
  calendar: CalendarResult | null
  onSelect: (name: string) => void
  onSearchFlights: (name: string, date?: string) => void
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

function formatDay(iso: string): string {
  const d = new Date(iso + 'T12:00:00')
  if (isNaN(d.getTime())) return iso
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

export function FlyDestinations({
  destinations,
  prices,
  selectedName,
  loading,
  flightsFor,
  flights,
  flightsLoading,
  calendar,
  onSelect,
  onSearchFlights,
}: Props) {
  const { t } = useI18n()

  const cheapestDays = useMemo(() => {
    if (!calendar) return []
    const today = new Date().toISOString().slice(0, 10)
    return [...calendar.days]
      .filter((d) => d.day >= today)
      .sort((a, b) => a.price - b.price)
      .slice(0, 6)
      .sort((a, b) => a.day.localeCompare(b.day))
  }, [calendar])

  if (destinations.length === 0) return null

  return (
    <div className="panel fly-panel">
      <h2>✈️ {t('fly.title')}</h2>
      <div className="fly-grid">
        {destinations.map((d) => {
          const active = d.name === selectedName
          const showFlights = flightsFor === d.name
          const price = prices[d.name]
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
                  {d.region}
                  <span className="fly-airport"> → {d.airport}</span>
                  {price && (
                    <span className="fly-price">
                      {' '}
                      · {t('fly.from')} {price.currency} {price.starting_price}
                    </span>
                  )}
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

              {showFlights && (
                <div className="fly-offers">
                  {cheapestDays.length > 0 && (
                    <div className="cal-chips">
                      <span className="cal-label">{t('fly.cheapestDays')}:</span>
                      {cheapestDays.map((cd) => (
                        <button
                          key={cd.day}
                          type="button"
                          className={`cal-chip cal-${cd.group}`}
                          disabled={flightsLoading}
                          onClick={() => onSearchFlights(d.name, cd.day)}
                          title={`${cd.day} · ${calendar?.currency} ${cd.price}`}
                        >
                          {formatDay(cd.day)} · ${cd.price}
                        </button>
                      ))}
                    </div>
                  )}
                  {flights && (
                    <>
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
                    </>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
