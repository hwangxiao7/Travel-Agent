import { useI18n } from '../i18n'
import type { Itinerary } from '../types'

interface Props {
  itinerary: Itinerary | null
}

export function ItineraryCard({ itinerary }: Props) {
  const { t } = useI18n()

  if (!itinerary) {
    return (
      <div className="panel itinerary-empty">
        <p>{t('itin.empty')}</p>
      </div>
    )
  }

  return (
    <div className="panel itinerary-card">
      <header>
        <h2>{itinerary.destination}</h2>
        <p className="meta">
          {itinerary.travel_mode === 'fly'
            ? `✈ ${itinerary.origin_airport} → ${itinerary.destination_airport} · ${itinerary.drive_time} ${t('itin.flight')}`
            : `${itinerary.drive_time} ${t('itin.drive')}`}{' '}
          · {itinerary.weather_note}
        </p>
        <p className="summary">{itinerary.summary}</p>
      </header>

      {itinerary.days.map((day) => (
        <section key={day.date} className="day-block">
          <h3>{day.date}</h3>
          <ol className="timeline">
            {day.activities.map((a) => (
              <li key={`${day.date}-${a.time}-${a.place}`}>
                <span className="time">{a.time}</span>
                <div>
                  <strong>{a.place}</strong>
                  <span className="dur">{a.duration}</span>
                  {a.note && <p className="note">{a.note}</p>}
                </div>
              </li>
            ))}
          </ol>
        </section>
      ))}

      {itinerary.alternatives.length > 0 && (
        <section>
          <h3>{t('itin.alternatives')}</h3>
          <ul className="alts">
            {itinerary.alternatives.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </section>
      )}

      {itinerary.packing_tips.length > 0 && (
        <section>
          <h3>{t('itin.pack')}</h3>
          <div className="tags readonly">
            {itinerary.packing_tips.map((t) => (
              <span key={t} className="tag active">{t}</span>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
