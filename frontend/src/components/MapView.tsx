import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useI18n } from '../i18n'
import type { Candidate, FlyDestination, Location, Place } from '../types'

interface Props {
  origin: Location
  candidates: Candidate[]
  selected?: { lat: number; lng: number; name: string } | null
  onSelect?: (name: string) => void
  food?: Place[]
  fun?: Place[]
  viral?: Place[]
  flyDestinations?: FlyDestination[]
}

function pin(color: string, label: string): L.DivIcon {
  return L.divIcon({
    className: 'map-pin',
    html: `<span class="pin-dot" style="background:${color}">${label}</span>`,
    iconSize: [26, 26],
    iconAnchor: [13, 13],
    popupAnchor: [0, -14],
  })
}

function dot(color: string): L.DivIcon {
  return L.divIcon({
    className: 'map-dot',
    html: `<span class="poi-dot" style="background:${color}"></span>`,
    iconSize: [14, 14],
    iconAnchor: [7, 7],
    popupAnchor: [0, -8],
  })
}

const FOOD_COLOR = '#e11d48'
const FUN_COLOR = '#7c3aed'
const FLY_COLOR = '#0891b2'
const VIRAL_COLOR = '#f97316'

export function MapView({
  origin,
  candidates,
  selected,
  onSelect,
  food = [],
  fun = [],
  viral = [],
  flyDestinations = [],
}: Props) {
  const { t } = useI18n()
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<L.Map | null>(null)
  const layerRef = useRef<L.LayerGroup | null>(null)
  const onSelectRef = useRef(onSelect)
  onSelectRef.current = onSelect

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    const map = L.map(containerRef.current, { scrollWheelZoom: false }).setView(
      [origin.lat, origin.lng],
      8,
    )
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 19,
    }).addTo(map)

    layerRef.current = L.layerGroup().addTo(map)
    mapRef.current = map

    return () => {
      map.remove()
      mapRef.current = null
      layerRef.current = null
    }
  }, [origin.lat, origin.lng])

  useEffect(() => {
    const map = mapRef.current
    const layer = layerRef.current
    if (!map || !layer) return

    layer.clearLayers()

    L.marker([origin.lat, origin.lng], { icon: pin('#2563eb', '★') })
      .bindPopup(`<strong>${t('map.start')}</strong><br/>${origin.label || ''}`)
      .addTo(layer)

    candidates.forEach((c, i) => {
      const isSelected = selected?.name === c.name
      const color = isSelected ? '#16a34a' : i === 0 ? '#ea580c' : '#64748b'
      const badge = i === 0 ? '✓' : String(i + 1)
      const marker = L.marker([c.lat, c.lng], { icon: pin(color, badge) })
        .bindPopup(
          `<strong>${c.name}</strong><br/>${c.drive_time} ${t('itin.drive')}<br/><em>${c.highlight}</em>`,
        )
        .addTo(layer)
      marker.on('click', () => onSelectRef.current?.(c.name))
    })

    flyDestinations.forEach((f) => {
      L.marker([f.lat, f.lng], { icon: pin(FLY_COLOR, '✈') })
        .bindPopup(`<strong>${f.name}</strong><br/>${f.flight_time} ${t('itin.flight')}<br/><em>${f.highlight}</em>`)
        .addTo(layer)
    })

    food.forEach((p) => {
      L.marker([p.lat, p.lng], { icon: dot(FOOD_COLOR) })
        .bindPopup(`🍴 <strong>${p.name}</strong>${p.note ? `<br/>${p.note}` : ''}`)
        .addTo(layer)
    })
    fun.forEach((p) => {
      L.marker([p.lat, p.lng], { icon: dot(FUN_COLOR) })
        .bindPopup(`📸 <strong>${p.name}</strong>${p.recommended ? `<br/>★ ${t('place.top')}` : ''}`)
        .addTo(layer)
    })
    viral.forEach((p) => {
      L.marker([p.lat, p.lng], { icon: pin(VIRAL_COLOR, '🔥') })
        .bindPopup(`🔥 <strong>${p.name}</strong><br/>${t('itin.viralTag')}`)
        .addTo(layer)
    })

    const points: L.LatLngExpression[] = [
      [origin.lat, origin.lng],
      ...candidates.map((c) => [c.lat, c.lng] as L.LatLngExpression),
      ...flyDestinations.map((f) => [f.lat, f.lng] as L.LatLngExpression),
      ...viral.map((p) => [p.lat, p.lng] as L.LatLngExpression),
    ]
    if (points.length > 1) {
      map.fitBounds(L.latLngBounds(points), { padding: [40, 40], maxZoom: 10 })
    } else {
      map.setView([origin.lat, origin.lng], 9)
    }
  }, [origin, candidates, selected, food, fun, viral, flyDestinations, t])

  return (
    <div className="map-wrap">
      <div ref={containerRef} className="map-container" />
      <div className="map-legend">
        <span><i className="lg" style={{ background: '#ea580c' }} />{t('map.recommended')}</span>
        <span><i className="lg" style={{ background: FOOD_COLOR }} />{t('itin.food')}</span>
        <span><i className="lg" style={{ background: FUN_COLOR }} />{t('itin.fun')}</span>
        {viral.length > 0 && (
          <span><i className="lg" style={{ background: VIRAL_COLOR }} />🔥</span>
        )}
        {flyDestinations.length > 0 && (
          <span><i className="lg" style={{ background: FLY_COLOR }} />{t('fly.title')}</span>
        )}
      </div>
    </div>
  )
}
