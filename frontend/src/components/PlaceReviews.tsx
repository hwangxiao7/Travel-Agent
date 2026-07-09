import { useEffect, useState } from 'react'
import {
  fetchPlaceReviews,
  upsertReview,
  type AuthUser,
  type PlaceReviewsResponse,
} from '../api/client'
import { useI18n } from '../i18n'

interface Props {
  placeName: string
  destination?: string
  user: AuthUser | null
}

export function PlaceReviews({ placeName, destination = '', user }: Props) {
  const { t } = useI18n()
  const [data, setData] = useState<PlaceReviewsResponse | null>(null)
  const [rating, setRating] = useState(5)
  const [comment, setComment] = useState('')
  const [msg, setMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const load = () => {
    fetchPlaceReviews(placeName)
      .then(setData)
      .catch(() => setData({ place_name: placeName, average_rating: 0, review_count: 0, reviews: [] }))
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [placeName])

  const submit = async () => {
    if (!user) {
      setMsg(t('auth.needLogin'))
      return
    }
    setBusy(true)
    setMsg(null)
    try {
      await upsertReview({ place_name: placeName, destination, rating, comment })
      setComment('')
      setMsg(t('review.saved'))
      load()
    } catch (e) {
      setMsg(e instanceof Error ? e.message : t('review.failed'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="place-reviews">
      <div className="review-summary">
        {data && data.review_count > 0 ? (
          <span>
            ★ {data.average_rating.toFixed(1)} · {data.review_count} {t('review.count')}
          </span>
        ) : (
          <span>{t('review.none')}</span>
        )}
      </div>
      <ul className="review-list">
        {(data?.reviews ?? []).slice(0, 5).map((r) => (
          <li key={r.id}>
            <strong>
              {'★'.repeat(r.rating)}
              {'☆'.repeat(5 - r.rating)}
            </strong>{' '}
            <em>{r.author}</em>
            {r.comment && <p>{r.comment}</p>}
          </li>
        ))}
      </ul>
      <div className="review-form">
        <label>
          {t('review.rating')}
          <select value={rating} onChange={(e) => setRating(Number(e.target.value))}>
            {[5, 4, 3, 2, 1].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
        <textarea
          rows={2}
          placeholder={t('review.placeholder')}
          value={comment}
          onChange={(e) => setComment(e.target.value)}
        />
        <button type="button" disabled={busy} onClick={submit}>
          {busy ? t('review.saving') : t('review.submit')}
        </button>
        {msg && <span className="review-msg">{msg}</span>}
      </div>
    </div>
  )
}
