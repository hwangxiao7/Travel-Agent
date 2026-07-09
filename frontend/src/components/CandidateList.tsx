import { useI18n } from '../i18n'
import type { Candidate } from '../types'

interface Props {
  candidates: Candidate[]
  selectedName: string | null
  loading: boolean
  onSelect: (name: string) => void
}

function userFacingWhy(c: Candidate): { highlight: string | null; reason: string | null } {
  // Prefer human explanation from RAG; never show internal score dumps.
  const reason =
    c.explanation && !/final_score|search_score|fusion/i.test(c.explanation)
      ? c.explanation
      : null
  const highlight = c.highlight || null
  // If explanation duplicates highlight, show once.
  if (reason && highlight && reason.trim() === highlight.trim()) {
    return { highlight, reason: null }
  }
  return { highlight, reason }
}

export function CandidateList({ candidates, selectedName, loading, onSelect }: Props) {
  const { t } = useI18n()
  if (candidates.length === 0) return null

  return (
    <div className="panel candidate-list">
      <h2>{t('cand.title')}</h2>
      <div className="candidate-grid">
        {candidates.map((c) => {
          const active = c.name === selectedName
          const { highlight, reason } = userFacingWhy(c)
          return (
            <button
              key={c.name}
              type="button"
              className={`candidate-card ${active ? 'active' : ''}`}
              disabled={loading}
              onClick={() => onSelect(c.name)}
            >
              <div className="candidate-head">
                <strong>{c.name}</strong>
                <span className="candidate-time">{c.drive_time}</span>
              </div>
              {highlight && <p className="candidate-highlight">{highlight}</p>}
              {reason && <p className="candidate-explain">{t('cand.why')}: {reason}</p>}
              {active && <span className="candidate-badge">✓ {t('cand.selected')}</span>}
            </button>
          )
        })}
      </div>
    </div>
  )
}
