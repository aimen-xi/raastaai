import { useEffect, useMemo, useState } from 'react'
import { ApiError, imageUrl, setStatus } from './api'
import { MapView } from './MapView'
import {
  aiSummary, applyFilters, CAT_COLOR, CAT_LABEL, formatWhen, locationSummary, NO_FILTERS, STATUS_LABEL, STATUSES, timeAgo, type Filters,
} from './logic'
import type { Cluster, Report, Status } from './types'

const PAGE = 25

/** `focus` (from a map popup or hotspot "View") pre-filters to a cluster; the page remounts per visit. */
export function Reports({ reports, clusters, focus }: {
  reports: Report[]
  clusters: Cluster[]
  focus: { clusterId: string } | null
}) {
  const [f, setF] = useState<Filters>(() => (focus ? { ...NO_FILTERS, q: focus.clusterId } : NO_FILTERS))
  const [page, setPage] = useState(0)
  const [selectedId, setSelectedId] = useState<string | null>(
    () => (focus ? reports.find((r) => r.clusterId === focus.clusterId)?.id ?? null : null),
  )

  const rows = useMemo(() => applyFilters(reports, f), [reports, f])
  const clusterById = useMemo(() => new Map(clusters.map((c) => [c.id, c])), [clusters])
  const pageRows = rows.slice(page * PAGE, page * PAGE + PAGE)
  const selected = reports.find((r) => r.id === selectedId) ?? null
  const set = (patch: Partial<Filters>) => {
    setF({ ...f, ...patch })
    setPage(0)
  }

  return (
    <>
      <div className="page-head">
        <h1>Reports</h1>
      </div>
      <div className="filters">
        <input placeholder="Search by report or cluster ID" value={f.q} onChange={(e) => set({ q: e.target.value })} aria-label="Search" />
        <select aria-label="Category" value={f.category} onChange={(e) => set({ category: e.target.value as Filters['category'] })}>
          <option value="all">All categories</option>
          <option value="pothole">Pothole</option>
          <option value="garbage">Garbage</option>
        </select>
        <select aria-label="Status" value={f.status} onChange={(e) => set({ status: e.target.value as Filters['status'] })}>
          <option value="all">All statuses</option>
          {STATUSES.map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}
        </select>
        <select aria-label="Verification" value={f.verification} onChange={(e) => set({ verification: e.target.value as Filters['verification'] })}>
          <option value="all">All verification</option>
          <option value="verified">AI-verified only</option>
          <option value="unverified">Unverified only</option>
          <option value="ai_rejected">AI found nothing only</option>
        </select>
        <select aria-label="Sort" value={f.sort} onChange={(e) => set({ sort: e.target.value as Filters['sort'] })}>
          <option value="priority">Priority (AI-verified first)</option>
          <option value="newest">Newest first</option>
        </select>
        <select aria-label="Location source" value={f.source} onChange={(e) => set({ source: e.target.value as Filters['source'] })}>
          <option value="all">GPS + manual pin</option>
          <option value="gps">GPS</option>
          <option value="manual_pin">Manual pin</option>
        </select>
        {JSON.stringify(f) !== JSON.stringify(NO_FILTERS) && <button className="link" onClick={() => set(NO_FILTERS)}>Clear</button>}
      </div>
      <div className="split">
        <div className="card table-card">
          <table>
            <thead>
              <tr>
                <th>ID</th><th>Category</th><th>AI result</th><th>Verification</th><th>Location</th><th>Cluster</th><th>Status</th><th>Reported</th>
              </tr>
            </thead>
            <tbody>
              {pageRows.map((r) => (
                <tr key={r.id} className={r.id === selectedId ? 'sel' : ''} onClick={() => setSelectedId(r.id)} tabIndex={0}
                  onKeyDown={(e) => e.key === 'Enter' && setSelectedId(r.id)}>
                  <td className="mono">{r.id}</td>
                  <td><CatBadge c={r.category} /></td>
                  <td>{aiSummary(r)}</td>
                  <td>
                    <VerBadge v={r.verification} />
                    {r.photoReusedFrom && <span className="badge muted" title={`Same photo as ${r.photoReusedFrom}`}> Photo seen before</span>}
                    {r.demoSample && <span className="badge muted" title="Bundled staged demo photo"> Demo photo</span>}
                  </td>
                  <td>{locationSummary(r)}</td>
                  <td className="mono">{r.clusterId} ({clusterById.get(r.clusterId)?.reportCount ?? 1})</td>
                  <td><StatusBadge s={r.status} /></td>
                  <td title={formatWhen(r.createdAt)}>{timeAgo(r.createdAt)}</td>
                </tr>
              ))}
              {!pageRows.length && (
                <tr><td colSpan={8} className="muted center-cell">No reports match these filters.</td></tr>
              )}
            </tbody>
          </table>
          <div className="pager">
            <span className="muted small">
              {rows.length ? `Showing ${page * PAGE + 1}–${Math.min(rows.length, (page + 1) * PAGE)} of ${rows.length}` : '0 reports'}
            </span>
            <span className="spacer" />
            <button className="btn" disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</button>
            <button className="btn" disabled={(page + 1) * PAGE >= rows.length} onClick={() => setPage(page + 1)}>Next</button>
          </div>
        </div>
        {selected ? (
          <Detail key={selected.id} r={selected} cluster={clusterById.get(selected.clusterId)} />
        ) : (
          <div className="card muted center-cell">Select a report to review it.</div>
        )}
      </div>
    </>
  )
}

function Detail({ r, cluster }: { r: Report; cluster?: Cluster }) {
  const [img, setImg] = useState<string | null>(null)
  const [imgErr, setImgErr] = useState<string | null>(null)
  const [next, setNext] = useState<Status>(r.status)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState<{ kind: 'ok' | 'err'; text: string } | null>(null)

  useEffect(() => {
    let url: string | null = null
    imageUrl(r.id).then(
      (u) => {
        url = u
        setImg(u)
      },
      (e: ApiError) => setImgErr(e.message),
    )
    return () => {
      if (url) URL.revokeObjectURL(url)
    }
  }, [r.id])

  async function save() {
    setSaving(true)
    setMsg(null)
    try {
      const res = await setStatus(r.id, next)
      setMsg({ kind: 'ok', text: res.changed ? `Status changed to ${STATUS_LABEL[res.status]}.` : 'Status unchanged.' })
    } catch (e) {
      const err = e as ApiError
      setMsg({
        kind: 'err',
        text: err.status === 403 ? 'Not authorised (403). Status not changed — your session has no admin role.' : err.message,
      })
    } finally {
      setSaving(false)
    }
  }

  const aiCat = r.aiCategory ? `${CAT_LABEL[r.aiCategory]} · ${Math.round((r.aiConfidence ?? 0) * 100)}%` : '—'
  const aiText = { issue: `${aiCat} (likely)`, uncertain: `${aiCat} (uncertain)`, not_issue: 'No road issue detected', error: 'AI unavailable' }[r.aiOutcome]
  const chose = (r.aiOutcome === 'issue' ? (r.userCorrected ? 'changed by citizen' : 'confirmed') : 'chosen manually') +
    (r.aiCheckedBy === 'server' ? ' · AI checked on the server (phone was offline)' : '')

  return (
    <aside className="card detail">
      <h2 className="mono">{r.id}</h2>
      <div className="photo">
        {img ? <img src={img} alt={`Report ${r.id} photo`} /> : <div className="muted center-cell">{imgErr ?? 'Loading photo…'}</div>}
      </div>
      <p className="muted small">Stored image · EXIF removed · {r.imageWidth} × {r.imageHeight}</p>
      <dl>
        <dt>AI suggestion</dt><dd>{aiText}</dd>
        <dt>Citizen chose</dt><dd><CatBadge c={r.category} /> {chose}</dd>
        <dt>Verification</dt><dd><VerBadge v={r.verification} /></dd>
        {r.photoReusedFrom && (
          <>
            <dt>Photo</dt>
            <dd><span className="badge muted">Photo seen before</span> same picture as <span className="mono">{r.photoReusedFrom}</span> (sent by another citizen at this spot)</dd>
          </>
        )}
        {r.demoSample && (
          <>
            <dt>Photo</dt>
            <dd><span className="badge muted">Demo photo</span> one of the app’s staged sample images</dd>
          </>
        )}
        <dt>Location</dt>
        <dd>
          {r.lat.toFixed(5)}, {r.lng.toFixed(5)} · {locationSummary(r)}
          {r.outsidePakistan && <span className="badge warn"> outside Pakistan</span>}
        </dd>
        <dt>Cluster</dt>
        <dd className="mono">
          {r.clusterId} · {cluster?.reportCount ?? 1} report{(cluster?.reportCount ?? 1) === 1 ? '' : 's'}
          {cluster?.isHotspot ? ' · hotspot' : ''}
        </dd>
        <dt>Reported</dt><dd>{formatWhen(r.createdAt)}</dd>
        {r.note && (<><dt>Note</dt><dd className="note">{r.note}</dd></>)}
      </dl>
      <MapView reports={[r]} clusters={cluster ? [cluster] : []} height={170} />
      <h3>Status</h3>
      <div className="seg">
        {STATUSES.map((s) => (
          <button key={s} className={s === next ? 'on' : ''} onClick={() => setNext(s)}>{STATUS_LABEL[s]}</button>
        ))}
      </div>
      <button className="btn primary" disabled={saving || next === r.status} onClick={save}>
        {saving ? 'Saving…' : 'Save status'}
      </button>
      {msg && <div className={`alert ${msg.kind}`}>{msg.text}</div>}
      <h3>History</h3>
      <ul className="history">
        <li>{formatWhen(r.createdAt)} · created by anonymous citizen{(cluster?.reportCount ?? 1) > 1 ? ` (cluster ${r.clusterId})` : ''}</li>
        <li>{formatWhen(r.createdAt)} · AI: {aiText} · citizen {chose}</li>
        {r.statusHistory.map((h, i) => (
          <li key={i}>{formatWhen(h.at)} · {STATUS_LABEL[h.from ?? 'pending']} → {STATUS_LABEL[h.to]} by admin</li>
        ))}
      </ul>
    </aside>
  )
}

function CatBadge({ c }: { c: Report['category'] }) {
  return (
    <span className="cat">
      <span className="dot" style={{ background: CAT_COLOR[c], borderRadius: c === 'pothole' ? 999 : 2 }} />
      {CAT_LABEL[c]}
    </span>
  )
}
const VER: Record<Report['verification'], [string, string, string]> = {
  verified: ['info', 'AI-verified', 'The AI found this problem and the citizen confirmed it.'],
  unverified: ['warn', 'Unverified', 'The AI was unsure or unavailable, or the citizen changed the category.'],
  ai_rejected: ['muted', 'AI found nothing', 'The AI found no pothole or garbage; the citizen reported it anyway with a note. Lowest priority; never counts toward a hotspot.'],
}
const VerBadge = ({ v }: { v: Report['verification'] }) => {
  const [cls, label, tip] = VER[v] ?? VER.unverified
  return <span className={`badge ${cls}`} title={tip}>{label}</span>
}
const StatusBadge = ({ s }: { s: Status }) => <span className={`badge st-${s}`}>{STATUS_LABEL[s]}</span>
