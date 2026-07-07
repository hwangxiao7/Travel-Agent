import type { Itinerary } from '../types'

interface Props {
  itinerary: Itinerary | null
}

export function ItineraryCard({ itinerary }: Props) {
  if (!itinerary) {
    return (
      <div className="panel itinerary-empty">
        <p>Fill in your constraints and hit <strong>Generate plan</strong> for a spontaneous itinerary.</p>
      </div>
    )
  }

  return (
    <div className="panel itinerary-card">
      <header>
        <h2>{itinerary.destination}</h2>
        <p className="meta">{itinerary.drive_time} drive · {itinerary.weather_note}</p>
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
          <h3>Alternatives</h3>
          <ul className="alts">
            {itinerary.alternatives.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </section>
      )}

      {itinerary.packing_tips.length > 0 && (
        <section>
          <h3>Pack</h3>
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
