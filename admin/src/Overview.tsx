import { useMemo, useState } from 'react'
import { MapView } from './MapView'
import { inPeriod, kpis, type Period } from './logic'
import type { Cluster, Report } from './types'
import { HotspotList } from './Hotspots'

export function Overview({ reports, clusters, onOpenCluster }: { reports: Report[]; clusters: Cluster[]; onOpenCluster: (id: string) => void }) {
  const [period, setPeriod] = useState<Period>('30d')
  const shown = useMemo(() => reports.filter((r) => inPeriod(r.createdAt, period)), [reports, period])
  const k = kpis(shown)
  const tiles = [
    { label: 'Total reports', value: k.total, sub: '', dot: '#1F2933', round: false },
    { label: 'Potholes', value: k.pothole, sub: `${k.potholeVerified} AI-verified`, dot: '#C2410C', round: true },
    { label: 'Garbage', value: k.garbage, sub: `${k.garbageVerified} AI-verified`, dot: '#1D4ED8', round: false },
    { label: 'Pending', value: k.pending, sub: `${k.needsReview} need review · ${k.aiRejected} AI found nothing`, dot: '#9AA5B1', round: true },
    { label: 'In progress', value: k.inProgress, sub: '', dot: '#F5B700', round: true },
    { label: 'Resolved', value: k.resolved, sub: '', dot: '#1F2933', round: true },
  ]
  return (
    <>
      <div className="page-head">
        <div>
          <h1>Overview</h1>
          <p className="muted">Pilot area · {period === 'all' ? 'all time' : period === '7d' ? 'last 7 days' : 'last 30 days'}</p>
        </div>
        <div className="seg">
          {(['30d', '7d', 'all'] as Period[]).map((p) => (
            <button key={p} className={p === period ? 'on' : ''} onClick={() => setPeriod(p)}>
              {p === 'all' ? 'All time' : p === '7d' ? 'Last 7 days' : 'Last 30 days'}
            </button>
          ))}
        </div>
      </div>
      <div className="kpis">
        {tiles.map((t) => (
          <div className="card kpi" key={t.label}>
            <div className="kpi-label">
              <span className="dot" style={{ background: t.dot, borderRadius: t.round ? 999 : 2 }} />
              {t.label}
            </div>
            <div className="kpi-value">{t.value}</div>
            <div className="muted small">{t.sub || ' '}</div>
          </div>
        ))}
      </div>
      <div className="grid2">
        <div className="card">
          <div className="card-head">
            <h2>Reports map</h2>
            <span className="legend">
              <i className="lg-p" /> Pothole <i className="lg-g" /> Garbage <i className="lg-h" /> Hotspot
            </span>
          </div>
          <MapView reports={shown} clusters={clusters} onOpenCluster={onOpenCluster} />
        </div>
        <div className="card">
          <h2>Recurring hotspots</h2>
          <p className="muted small">Hotspot = 3+ reports within 50 m in 30 days. Reports merge into one cluster within 25 m and 7 days.</p>
          <HotspotList clusters={clusters} onOpenCluster={onOpenCluster} limit={6} />
        </div>
      </div>
    </>
  )
}
