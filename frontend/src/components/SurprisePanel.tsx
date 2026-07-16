import { useEffect, useState, useSyncExternalStore } from 'react'
import { fetchActivities, fetchActivityVenues } from '../api/client'
import { useI18n } from '../i18n'
import { isLiked, likesVersion, setLikeOrigin, subscribeLikes, toggleLike } from '../likes'
import type { ActivityIdea, ActivityVenue, Location } from '../types'
import { AssetImg } from './AssetImg'

interface Props {
  origin: Location
}

const ENERGIES = ['', 'low', 'medium', 'high'] as const
const COMPANIONS = ['', 'solo', 'date', 'family', 'friends'] as const

export function SurprisePanel({ origin }: Props) {
  const { t, lang } = useI18n()
  const [mood, setMood] = useState('')
  const [energy, setEnergy] = useState('')
  const [companion, setCompanion] = useState('')
  const [ideas, setIdeas] = useState<ActivityIdea[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [venues, setVenues] = useState<Record<string, ActivityVenue[]>>({})
  const [venueLoading, setVenueLoading] = useState<string | null>(null)
  const likeTick = useSyncExternalStore(subscribeLikes, likesVersion)
  void likeTick

  useEffect(() => {
    setLikeOrigin(origin)
  }, [origin])

  const load = async (interests = mood) => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetchActivities({
        interests,
        energy,
        companion,
        language: lang,
      })
      setIdeas(res.activities)
      setExpanded(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load('')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang])

  const toggleVenues = async (idea: ActivityIdea) => {
    if (expanded === idea.key) {
      setExpanded(null)
      return
    }
    setExpanded(idea.key)
    if (venues[idea.key]) return
    setVenueLoading(idea.key)
    try {
      const res = await fetchActivityVenues({
        activity_key: idea.key,
        origin,
        language: lang,
      })
      setVenues((v) => ({ ...v, [idea.key]: res.venues }))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed')
    } finally {
      setVenueLoading(null)
    }
  }

  const energyLabel = (e: string) => {
    if (!e) return t('surprise.any')
    if (lang === 'zh') {
      return ({ low: '轻松', medium: '适中', high: '嗨' } as Record<string, string>)[e] ?? e
    }
    return e.charAt(0).toUpperCase() + e.slice(1)
  }

  const companionLabel = (c: string) => {
    if (!c) return t('surprise.any')
    if (lang === 'zh') {
      return (
        ({ solo: '独自', date: '约会', family: '亲子', friends: '朋友' } as Record<string, string>)[
          c
        ] ?? c
      )
    }
    return c.charAt(0).toUpperCase() + c.slice(1)
  }

  return (
    <section className="sticker mint">
      <h2 className="card-title">🎲 {t('surprise.title')}</h2>
      <p className="muted">{t('surprise.hint')}</p>

      <div className="picker-row">
        <label>
          {t('surprise.energy')}
          <select value={energy} onChange={(e) => setEnergy(e.target.value)}>
            {ENERGIES.map((e) => (
              <option key={e || 'any'} value={e}>
                {energyLabel(e)}
              </option>
            ))}
          </select>
        </label>
        <label>
          {t('surprise.with')}
          <select value={companion} onChange={(e) => setCompanion(e.target.value)}>
            {COMPANIONS.map((c) => (
              <option key={c || 'any'} value={c}>
                {companionLabel(c)}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="mood-row">
        <input
          value={mood}
          onChange={(e) => setMood(e.target.value)}
          placeholder={t('surprise.moodPh')}
        />
        <button type="button" className="pill" onClick={() => void load()} disabled={loading}>
          {t('surprise.match')}
        </button>
      </div>

      <button type="button" className="pill primary" onClick={() => void load('')} disabled={loading}>
        {t('surprise.cta')}
      </button>

      {error && <p className="error-text">{error}</p>}
      {loading && <p className="muted">{t('cand.planning')}</p>}

      <ul className="idea-list">
        {ideas.map((idea) => (
          <li
            key={idea.key}
            className={`idea-card${isLiked('activity', idea.key) ? ' liked' : ''}`}
            onDoubleClick={() =>
              toggleLike({
                kind: 'activity',
                key: idea.key,
                name: idea.name,
                tags: idea.tags,
                blurb: idea.reason || idea.blurb || '',
              })
            }
            title={lang === 'zh' ? '双击标记喜欢' : 'Double-click to like'}
          >
            <div className="idea-head">
              <AssetImg iconKey={idea.icon_key || 'mascot'} alt={idea.name} size={48} />
              <strong>
                {idea.name}
                {isLiked('activity', idea.key) ? <span className="like-heart">♥</span> : null}
              </strong>
              <span className="chip">{idea.duration_h ? `${idea.duration_h}h` : ''}</span>
            </div>
            {(idea.blurb || idea.reason) && (
              <p className="muted small">{idea.reason || idea.blurb}</p>
            )}
            <div className="chip-row">
              {idea.energy && <span className="chip soft">{idea.energy}</span>}
              {idea.cost && <span className="chip soft">{idea.cost}</span>}
              {idea.indoor ? <span className="chip soft">indoor</span> : null}
            </div>
            <button
              type="button"
              className="pill ghost"
              onClick={() => void toggleVenues(idea)}
              disabled={venueLoading === idea.key}
            >
              {venueLoading === idea.key
                ? t('surprise.finding')
                : expanded === idea.key
                  ? t('surprise.hide')
                  : t('surprise.nearby')}
            </button>
            {expanded === idea.key && (
              <ul className="venue-list">
                {(venues[idea.key] || []).map((v) => (
                  <li key={`${v.name}-${v.lat}`}>
                    <strong>{v.name}</strong>
                    <span className="muted small">
                      {v.drive_time || `${v.distance_miles.toFixed(1)} mi`}
                    </span>
                    {v.blurb && <p className="muted small">{v.blurb}</p>}
                  </li>
                ))}
                {(venues[idea.key] || []).length === 0 && venueLoading !== idea.key && (
                  <li className="muted small">—</li>
                )}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}
