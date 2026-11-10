// Pure helpers (unit-tested in logic.test.ts): labels, filters, KPIs.
import type { Category, Cluster, Report, Status, Verification } from './types'

export const CAT_LABEL: Record<Category, string> = { pothole: 'Pothole', garbage: 'Garbage' }
export const CAT_COLOR: Record<Category, string> = { pothole: '#C2410C', garbage: '#1D4ED8' }
export const STATUS_LABEL: Record<Status, string> = { pending: 'Pending', in_progress: 'In progress', resolved: 'Resolved' }
export const STATUSES: Status[] = ['pending', 'in_progress', 'resolved']

const DAY = 86_400_000
export const HOTSPOT_WINDOW_DAYS = 30

export type Period = '7d' | '30d' | 'all'

export function inPeriod(d: Date, period: Period, now = new Date()): boolean {
  if (period === 'all') return true
  return now.getTime() - d.getTime() <= (period === '7d' ? 7 : 30) * DAY
}

export function aiSummary(r: Report): string {
  const pct = r.aiConfidence == null ? '' : ` · ${Math.round(r.aiConfidence * 100)}%`
  switch (r.aiOutcome) {
    case 'issue':
      return r.userCorrected ? `AI said ${r.aiCategory}${pct} · citizen changed` : `Likely${pct}`
    case 'uncertain':
      return `Uncertain${pct}`
    case 'not_issue':
      return 'Not issue · manual'
    default:
      return 'Failed · manual'
  }
}

export function locationSummary(r: Report): string {
  return r.locationSource === 'gps' ? `GPS ±${Math.round(r.accuracyM ?? 0)} m` : 'Manual pin'
}

export function timeAgo(d: Date, now = new Date()): string {
  const s = Math.max(0, (now.getTime() - d.getTime()) / 1000)
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)} min ago`
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`
  return `${Math.floor(s / 86400)} d ago`
}

export function formatWhen(d: Date): string {
  return d.toLocaleString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export interface Filters {
  q: string
  category: Category | 'all'
  status: Status | 'all'
  verification: 'all' | Verification
  sort: 'priority' | 'newest'
  source: 'all' | 'gps' | 'manual_pin'
}

export const NO_FILTERS: Filters = { q: '', category: 'all', status: 'all', verification: 'all', source: 'all', sort: 'priority' }

/** Review order: AI-verified first, then unverified, then "AI found nothing" (spam-resistant). */
export const VERIFICATION_RANK: Record<Verification, number> = { verified: 0, unverified: 1, ai_rejected: 2 }

export function applyFilters(reports: Report[], f: Filters): Report[] {
  const q = f.q.trim().toUpperCase()
  const rows = reports.filter(
    (r) =>
      (!q || r.id.toUpperCase().includes(q) || r.clusterId.toUpperCase().includes(q)) &&
      (f.category === 'all' || r.category === f.category) &&
      (f.status === 'all' || r.status === f.status) &&
      (f.verification === 'all' || r.verification === f.verification) &&
      (f.source === 'all' || r.locationSource === f.source),
  )
  const newest = (a: Report, b: Report) => b.createdAt.getTime() - a.createdAt.getTime()
  return f.sort === 'newest'
    ? rows.sort(newest)
    : rows.sort((a, b) => (VERIFICATION_RANK[a.verification] ?? 1) - (VERIFICATION_RANK[b.verification] ?? 1) || newest(a, b))
}

export function isActiveHotspot(c: Cluster, now = new Date()): boolean {
  return c.isHotspot && now.getTime() - c.lastAt.getTime() <= HOTSPOT_WINDOW_DAYS * DAY
}

function metres(aLat: number, aLng: number, bLat: number, bLng: number): number {
  const r = Math.PI / 180
  const x = (bLng - aLng) * r * Math.cos(((aLat + bLat) / 2) * r)
  const y = (bLat - aLat) * r
  return Math.sqrt(x * x + y * y) * 6_371_008.8
}

/** One entry per hotspot AREA: clusters of the same category whose centres are within 50 m are
 *  the same recurring spot (a far-ish duplicate starts its own cluster but feeds the same hotspot). */
export function hotspotAreas(clusters: Cluster[], now = new Date()): { lead: Cluster; members: Cluster[] }[] {
  const hot = clusters
    .filter((c) => isActiveHotspot(c, now))
    .sort((a, b) => b.nearbyCount30d - a.nearbyCount30d || b.lastAt.getTime() - a.lastAt.getTime())
  const areas: { lead: Cluster; members: Cluster[] }[] = []
  for (const c of hot) {
    const a = areas.find(
      (x) => x.lead.category === c.category && metres(x.lead.centroidLat, x.lead.centroidLng, c.centroidLat, c.centroidLng) <= 50,
    )
    if (a) a.members.push(c)
    else areas.push({ lead: c, members: [c] })
  }
  return areas
}

export interface Kpis {
  total: number
  pothole: number
  potholeVerified: number
  garbage: number
  garbageVerified: number
  pending: number
  needsReview: number
  aiRejected: number
  inProgress: number
  resolved: number
}

export function kpis(reports: Report[]): Kpis {
  const k: Kpis = { total: 0, pothole: 0, potholeVerified: 0, garbage: 0, garbageVerified: 0, pending: 0, needsReview: 0, aiRejected: 0, inProgress: 0, resolved: 0 }
  for (const r of reports) {
    k.total++
    const v = r.verification === 'verified'
    if (r.category === 'pothole') {
      k.pothole++
      if (v) k.potholeVerified++
    } else {
      k.garbage++
      if (v) k.garbageVerified++
    }
    if (r.verification === 'ai_rejected') k.aiRejected++
    if (r.status === 'pending') {
      k.pending++
      if (!v) k.needsReview++
    } else if (r.status === 'in_progress') k.inProgress++
    else k.resolved++
  }
  return k
}
