import { useI18n } from '../i18n'
import type { HomeModule } from '../types'

interface Props {
  module: HomeModule
  onChange: (m: HomeModule) => void
}

export function ModeSwitcher({ module, onChange }: Props) {
  const { t } = useI18n()
  return (
    <div className="mode-switcher">
      <button
        type="button"
        className={`mode-tile ${module === 'surprise' ? 'active' : ''}`}
        onClick={() => onChange('surprise')}
      >
        <span className="mode-icon" aria-hidden>
          🎲
        </span>
        <strong>{t('mode.surprise')}</strong>
        <span className="mode-cap">{t('mode.surpriseCap')}</span>
      </button>
      <button
        type="button"
        className={`mode-tile ${module === 'planner' ? 'active' : ''}`}
        onClick={() => onChange('planner')}
      >
        <span className="mode-icon" aria-hidden>
          🗺️
        </span>
        <strong>{t('mode.planner')}</strong>
        <span className="mode-cap">{t('mode.plannerCap')}</span>
      </button>
    </div>
  )
}
