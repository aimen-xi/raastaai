import 'leaflet/dist/leaflet.css'
import { Circle, CircleMarker, MapContainer, Popup, Rectangle, TileLayer, useMap } from 'react-leaflet'
import { useEffect } from 'react'
import type { LatLngBoundsExpression } from 'leaflet'
import { CAT_COLOR, CAT_LABEL, STATUS_LABEL, hotspotAreas } from './logic'
import type { Cluster, Report } from './types'

const LAHORE: [number, number] = [31.5204, 74.3587]

function FitTo({ points }: { points: [number, number][] }) {
  const map = useMap()
  const key = points.length
  // Leaflet measures its container once; re-measure whenever the layout resizes it
  // (otherwise parts of the map stay grey).
  useEffect(() => {
    const ro = new ResizeObserver(() => map.invalidateSize())
    ro.observe(map.getContainer())
    return () => ro.disconnect()
  }, [map])
  useEffect(() => {
    map.invalidateSize()
    if (points.length === 1) map.setView(points[0], 16)
    else if (points.length > 1) map.fitBounds(points as LatLngBoundsExpression, { padding: [30, 30], maxZoom: 16 })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, map])
  return null
}

/** Pothole = orange circle, garbage = blue square (shape + colour, not colour alone). */
export function MapView({ reports, clusters, onOpenCluster, height = 420 }: {
  reports: Report[]
  clusters: Cluster[]
  onOpenCluster?: (id: string) => void
  height?: number
}) {
  const pts = reports.map((r) => [r.lat, r.lng] as [number, number])
  const deg = 0.00004 // ~4.5 m half-size squares for garbage
  return (
    <MapContainer center={LAHORE} zoom={12} style={{ height, borderRadius: 14 }} scrollWheelZoom>
      <TileLayer
        // Esri World Street Map: free, no API key (CARTO now needs one; OSM's servers block app traffic)
        url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}"
        attribution="Tiles &copy; Esri &mdash; Sources: Esri, HERE, Garmin, &copy; OpenStreetMap contributors"
        maxNativeZoom={19}
        maxZoom={20}
      />
      <FitTo points={pts} />
      {hotspotAreas(clusters).map(({ lead: c }) => (
        <Circle key={c.id} center={[c.centroidLat, c.centroidLng]} radius={50}
          pathOptions={{ color: '#F5B700', weight: 2, dashArray: '4 4', fillColor: '#F5B700', fillOpacity: 0.12 }}>
          <Popup>
            <strong>Hotspot · {CAT_LABEL[c.category]}</strong>
            <br />
            {c.nearbyCount30d} reports within 50 m (30 days)
            <br />
            {onOpenCluster && <button className="link" onClick={() => onOpenCluster(c.id)}>View reports</button>}
          </Popup>
        </Circle>
      ))}
      {reports.map((r) => {
        const style = { color: '#fff', weight: 2, fillColor: CAT_COLOR[r.category], fillOpacity: r.status === 'resolved' ? 0.35 : 0.95 }
        const popup = (
          <Popup>
            <strong>{r.id}</strong> · {CAT_LABEL[r.category]}
            <br />
            {STATUS_LABEL[r.status]} · cluster {r.clusterId}
            <br />
            {onOpenCluster && <button className="link" onClick={() => onOpenCluster(r.clusterId)}>Open</button>}
          </Popup>
        )
        return r.category === 'pothole' ? (
          <CircleMarker key={r.id} center={[r.lat, r.lng]} radius={7} pathOptions={style}>{popup}</CircleMarker>
        ) : (
          <Rectangle key={r.id} bounds={[[r.lat - deg, r.lng - deg], [r.lat + deg, r.lng + deg]]} pathOptions={style}>{popup}</Rectangle>
        )
      })}
    </MapContainer>
  )
}
