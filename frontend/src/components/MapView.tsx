import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useI18n } from '../i18n'
import type { Candidate, Location } from '../types'

interface Props {
  origin: Location
  candidates: Candidate[]
  selected?: { lat: number; lng: number; name: string } | null
  onSelect?: (name: string) => void
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

export function MapView({ origin, candidates, selected, onSelect }: Props) {
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

    const points: L.LatLngExpression[] = [
      [origin.lat, origin.lng],
      ...candidates.map((c) => [c.lat, c.lng] as L.LatLngExpression),
    ]
    if (points.length > 1) {
      map.fitBounds(L.latLngBounds(points), { padding: [40, 40], maxZoom: 10 })
    } else {
      map.setView([origin.lat, origin.lng], 9)
    }
  }, [origin, candidates, selected, t])

  return <div ref={containerRef} className="map-container" />
}
