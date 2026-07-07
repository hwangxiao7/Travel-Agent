import { useI18n } from '../i18n'
import type { Candidate } from '../types'

interface Props {
  candidates: Candidate[]
  selectedName: string | null
  loading: boolean
  onSelect: (name: string) => void
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
              <p className="candidate-highlight">{c.highlight}</p>
              {active && <span className="candidate-badge">✓ {t('cand.selected')}</span>}
            </button>
          )
        })}
      </div>
    </div>
  )
}
