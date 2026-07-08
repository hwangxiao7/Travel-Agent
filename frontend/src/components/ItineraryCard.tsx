import { useState } from 'react'
import { useI18n } from '../i18n'
import type { EventItem, Itinerary, Location, Place, SocialPost } from '../types'
import { copyShareText, downloadICS, googleMapsUrl } from '../utils/export'

function compact(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

interface Props {
  itinerary: Itinerary | null
  origin?: Location
}

const CATEGORY_ICON: Record<string, string> = {
  restaurant: '🍽️',
  cafe: '☕',
  fast_food: '🍔',
  bar: '🍸',
  ice_cream: '🍦',
  museum: '🏛️',
  viewpoint: '🌄',
  attraction: '📸',
  artwork: '🎨',
  gallery: '🖼️',
  theme_park: '🎢',
  zoo: '🦁',
  aquarium: '🐠',
  park: '🌳',
  bakery: '🥐',
  sweets: '🍬',
  deli: '🥪',
  historic: '🏛️',
  shop: '🛍️',
  market: '🧺',
  theatre: '🎭',
  walk: '🚶',
}

export function ItineraryCard({ itinerary, origin }: Props) {
  const { t } = useI18n()
  const [copied, setCopied] = useState(false)

  const catLabel = (c: string) => t(`place.${c}`)

  const handleCopy = async () => {
    if (!itinerary) return
    const ok = await copyShareText(itinerary)
    if (ok) {
      setCopied(true)
      setTimeout(() => setCopied(false), 1800)
    }
  }

  const renderPlaces = (places: Place[], title: string) =>
    places.length > 0 && (
      <section>
        <h3>{title}</h3>
        <ul className="places">
          {places.map((p) => (
            <li key={`${p.kind}-${p.name}-${p.lat}`} className="place-item">
              <span className="place-icon">{CATEGORY_ICON[p.category] ?? '📍'}</span>
              <div>
                <strong>{p.name}</strong>
                {p.recommended && <span className="place-badge">{t('place.top')}</span>}
                <span className="place-cat">
                  {catLabel(p.category)}
                  {p.note ? ` · ${p.note}` : ''}
                </span>
              </div>
            </li>
          ))}
        </ul>
      </section>
    )

  const renderViral = (places: Place[]) =>
    places.length > 0 && (
      <section>
        <h3>{t('itin.viral')}</h3>
        <ul className="places">
          {places.map((p) => (
            <li key={`viral-${p.name}-${p.lat}`} className="place-item">
              <span className="place-icon">🔥</span>
              <div>
                <strong>{p.name}</strong>
                <span className="place-cat">
                  {p.kind === 'food' ? t('itin.food') : t('itin.fun')} · {t('itin.viralTag')}
                </span>
              </div>
            </li>
          ))}
        </ul>
      </section>
    )

  const renderGuides = (guides: SocialPost[]) =>
    guides.length > 0 && (
      <section>
        <h3>{t('itin.guides')}</h3>
        <ul className="guides">
          {guides.map((g) => (
            <li key={g.url || g.title} className="guide-item">
              <a href={g.url} target="_blank" rel="noreferrer">
                {g.title}
              </a>
              <span className="guide-meta">
                {[g.author && `@${g.author}`, g.views ? `▶ ${compact(g.views)}` : '', g.likes ? `♥ ${compact(g.likes)}` : '']
                  .filter(Boolean)
                  .join(' · ')}
              </span>
            </li>
          ))}
        </ul>
      </section>
    )

  const renderEvents = (events: EventItem[]) =>
    events.length > 0 && (
      <section>
        <h3>{t('itin.events')}</h3>
        <ul className="events">
          {events.map((e) => (
            <li key={`${e.name}-${e.date}`} className="event-item">
              <div>
                <strong>
                  {e.url ? (
                    <a href={e.url} target="_blank" rel="noreferrer">
                      {e.name}
                    </a>
                  ) : (
                    e.name
                  )}
                </strong>
                <span className="event-meta">
                  {[e.date, e.venue, e.category].filter(Boolean).join(' · ')}
                </span>
              </div>
            </li>
          ))}
        </ul>
      </section>
    )

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
        <div className="itin-actions">
          <button type="button" onClick={() => downloadICS(itinerary)}>
            {t('itin.export')}
          </button>
          <a
            className="btn-link"
            href={googleMapsUrl(origin, itinerary)}
            target="_blank"
            rel="noreferrer"
          >
            {t('itin.maps')}
          </a>
          <button type="button" onClick={handleCopy}>
            {copied ? t('itin.copied') : t('itin.copy')}
          </button>
        </div>
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

      {renderViral(itinerary.viral)}
      {renderEvents(itinerary.events)}
      {renderPlaces(itinerary.nearby_food, t('itin.food'))}
      {renderPlaces(itinerary.nearby_fun, t('itin.fun'))}
      {renderGuides(itinerary.guides)}

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
