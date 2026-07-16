import { useI18n } from '../i18n'
import type { Candidate, Itinerary } from '../types'

interface Props {
  candidates: Candidate[]
  expandedName: string | null
  itineraries: Record<string, Itinerary>
  detailLoading: string | null
  searchPath?: string | null
  onToggle: (c: Candidate) => void
}

const ORDER = ['local', 'regional', 'distant', 'fly'] as const

function groupKey(c: Candidate) {
  if (c.display_group) return c.display_group
  if (c.travel_mode === 'fly') return 'fly'
  return c.trip_scope || 'local'
}

function iconFor(c: Candidate) {
  const tags = c.semantic_tags || []
  for (const t of tags) {
    if (t === 'national-park') return '/icons/icon-national-park.webp'
    if (t === 'hiking') return '/icons/icon-hiking.webp'
    if (t === 'city-walk') return '/icons/icon-city-walk.webp'
    if (t === 'forest') return '/icons/icon-forest.webp'
    if (t === 'beach') return '/icons/icon-beach.webp'
  }
  return '/icons/mascot.webp'
}

export function CandidatesAccordion({
  candidates,
  expandedName,
  itineraries,
  detailLoading,
  searchPath,
  onToggle,
}: Props) {
  const { t } = useI18n()
  if (!candidates.length) return null

  const buckets = new Map<string, Candidate[]>()
  for (const c of candidates) {
    const k = groupKey(c)
    const list = buckets.get(k) || []
    list.push(c)
    buckets.set(k, list)
  }
  const groups = ORDER.filter((k) => (buckets.get(k) || []).length).map((k) => ({
    scope: k,
    items: buckets.get(k)!,
  }))
  const showAway =
    groups.some((g) => g.scope === 'distant' || g.scope === 'fly') &&
    groups.some((g) => g.scope === 'local' || g.scope === 'regional')
  let sawAway = false

  return (
    <section className="sticker mint" id="results">
      <h2 className="card-title">
        📍 {searchPath === 'poi' ? t('cand.nearby') : t('cand.title')}
      </h2>
      {groups.map(({ scope, items }) => {
        const banner = showAway && (scope === 'distant' || scope === 'fly') && !sawAway
        if (banner) sawAway = true
        return (
          <div key={scope} className="cand-group">
            {banner && <h3 className="kind-title">{t('cand.kind.away')}</h3>}
            {groups.length > 1 && (
              <h3 className="scope-title">{t(`cand.scope.${scope}` as 'cand.scope.local')}</h3>
            )}
            {items.map((c) => {
              const open = expandedName === c.name
              const it = itineraries[c.name]
              return (
                <div key={c.name} className={`cand-row ${open ? 'open' : ''}`}>
                  <button type="button" className="cand-btn" onClick={() => onToggle(c)}>
                    <img className="cand-thumb" src={iconFor(c)} alt="" />
                    <div className="cand-main">
                      <div className="cand-top">
                        <strong>{c.name}</strong>
                        <span className="cand-time">
                          {c.travel_mode === 'fly' ? `✈ ${c.drive_time}` : c.drive_time}
                        </span>
                        <span className="chev">{open ? '▴' : '▾'}</span>
                      </div>
                      {c.highlight && <p className="muted small">{c.highlight}</p>}
                      {c.explanation && (
                        <p className="muted small">
                          💡 {t('cand.why')}: {c.explanation}
                        </p>
                      )}
                    </div>
                  </button>
                  {open && (
                    <div className="itin-detail">
                      {detailLoading === c.name && !it && (
                        <p className="muted">{t('cand.planning')}</p>
                      )}
                      {it && (
                        <>
                          {it.summary && <p>{it.summary}</p>}
                          {it.weather_note && <p className="muted small">🌤 {it.weather_note}</p>}
                          {it.days.map((d) => (
                            <div key={d.date} className="day-block">
                              <h4>{d.date}</h4>
                              <ul>
                                {d.activities.map((a, i) => (
                                  <li key={`${a.time}-${i}`}>
                                    <strong>{a.time}</strong> {a.place}
                                    {a.duration ? ` · ${a.duration}` : ''}
                                    {a.note ? <span className="muted"> — {a.note}</span> : null}
                                  </li>
                                ))}
                              </ul>
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
        )
      })}
    </section>
  )
}
