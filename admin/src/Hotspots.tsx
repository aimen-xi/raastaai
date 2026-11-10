import { CAT_COLOR, CAT_LABEL, hotspotAreas, timeAgo } from './logic'
import type { Cluster } from './types'

export function HotspotList({ clusters, onOpenCluster, limit }: { clusters: Cluster[]; onOpenCluster: (id: string) => void; limit?: number }) {
  const areas = hotspotAreas(clusters).slice(0, limit ?? Infinity)
  if (!areas.length) return <p className="muted">No hotspots yet. A spot becomes one when 3 reports land within 50 m in 30 days.</p>
  return (
    <ul className="hot-list">
      {areas.map(({ lead, members }) => {
        const last = new Date(Math.max(...members.map((m) => m.lastAt.getTime())))
        const ids = members.map((m) => `${m.id} (${m.reportCount})`).join(', ')
        return (
          <li key={lead.id}>
            <span className="hot-count" title="Reports within 50 m in the last 30 days"
              style={{ background: CAT_COLOR[lead.category], borderRadius: lead.category === 'pothole' ? 999 : 8 }}>
              {lead.nearbyCount30d}
            </span>
            <div className="grow">
              <strong>{lead.centroidLat.toFixed(4)}, {lead.centroidLng.toFixed(4)}</strong>
              <div className="muted small">
                {CAT_LABEL[lead.category]} · {members.length > 1 ? 'clusters' : 'cluster'} {ids} · last report {timeAgo(last)}
              </div>
            </div>
            <button className="link" onClick={() => onOpenCluster(lead.id)}>View</button>
          </li>
        )
      })}
    </ul>
  )
}

export function Hotspots({ clusters, onOpenCluster }: { clusters: Cluster[]; onOpenCluster: (id: string) => void }) {
  return (
    <>
      <div className="page-head">
        <div>
          <h1>Hotspots</h1>
          <p className="muted">Recurring problem areas: 3 or more same-category reports within 50 m in the last 30 days.</p>
        </div>
      </div>
      <div className="card">
        <HotspotList clusters={clusters} onOpenCluster={onOpenCluster} />
      </div>
    </>
  )
}
