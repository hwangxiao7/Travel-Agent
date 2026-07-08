import { useEffect, useRef, useState } from 'react'
import { apiUrl } from '../api/endpoints'
import { useI18n } from '../i18n'
import type { Location } from '../types'

interface Props {
  value: string
  onSelect: (loc: Location) => void
  onTextChange: (text: string) => void
}

interface Suggestion {
  label: string
  lat: number
  lng: number
}

export function AddressSearch({ value, onSelect, onTextChange }: Props) {
  const { t } = useI18n()
  const [suggestions, setSuggestions] = useState<Suggestion[]>([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const boxRef = useRef<HTMLDivElement>(null)
  const skipNextFetch = useRef(false)

  useEffect(() => {
    if (skipNextFetch.current) {
      skipNextFetch.current = false
      return
    }
    const q = value.trim()
    if (q.length < 3) {
      setSuggestions([])
      return
    }
    const timer = setTimeout(async () => {
      setLoading(true)
      try {
        const res = await fetch(apiUrl('geocode', { q }))
        const data = await res.json()
        setSuggestions(data.results || [])
        setOpen(true)
      } catch {
        setSuggestions([])
      } finally {
        setLoading(false)
      }
    }, 350)
    return () => clearTimeout(timer)
  }, [value])

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const pick = (s: Suggestion) => {
    skipNextFetch.current = true
    onSelect({ label: s.label, lat: s.lat, lng: s.lng })
    setOpen(false)
    setSuggestions([])
  }

  return (
    <div className="address-search" ref={boxRef}>
      <input
        value={value}
        onChange={(e) => onTextChange(e.target.value)}
        onFocus={() => suggestions.length > 0 && setOpen(true)}
        placeholder={t('addr.placeholder')}
        autoComplete="off"
      />
      {loading && <span className="addr-spinner">…</span>}
      {open && suggestions.length > 0 && (
        <ul className="addr-list">
          {suggestions.map((s, i) => (
            <li key={`${s.lat}-${s.lng}-${i}`} onMouseDown={() => pick(s)}>
              {s.label}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
