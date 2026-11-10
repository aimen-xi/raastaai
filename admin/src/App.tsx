import { onIdTokenChanged, signOut, type User } from 'firebase/auth'
import { useEffect, useState } from 'react'
import { auth, MAX_REPORTS, watchClusters, watchReports } from './firebase'
import { Hotspots } from './Hotspots'
import { Login } from './Login'
import { Overview } from './Overview'
import { Reports } from './Reports'
import type { Cluster, Report } from './types'

type Tab = 'overview' | 'reports' | 'hotspots'
type Gate = { state: 'loading' } | { state: 'out' } | { state: 'denied'; user: User } | { state: 'admin'; user: User }

export default function App() {
  const [gate, setGate] = useState<Gate>({ state: 'loading' })

  useEffect(
    () =>
      onIdTokenChanged(auth, async (user) => {
        if (!user || user.isAnonymous) return setGate({ state: 'out' })
        const t = await user.getIdTokenResult()
        setGate(t.claims.admin === true ? { state: 'admin', user } : { state: 'denied', user })
      }),
    [],
  )

  if (gate.state === 'loading') return <div className="center muted">Loading…</div>
  if (gate.state !== 'admin') return <Login denied={gate.state === 'denied' ? gate.user.email : null} />
  return <Dashboard user={gate.user} />
}

function Dashboard({ user }: { user: User }) {
  const [tab, setTab] = useState<Tab>('overview')
  const [reports, setReports] = useState<Report[] | null>(null)
  const [clusters, setClusters] = useState<Cluster[]>([])
  const [error, setError] = useState<string | null>(null)
  const [focus, setFocus] = useState<{ clusterId: string } | null>(null)

  useEffect(() => {
    const onErr = (e: Error) => setError(e.message.includes('permission') ? 'Firestore refused access: this account has no admin role.' : e.message)
    const a = watchReports(setReports, onErr)
    const b = watchClusters(setClusters, onErr)
    return () => {
      a()
      b()
    }
  }, [])

  const openCluster = (clusterId: string) => {
    setFocus({ clusterId })
    setTab('reports')
  }

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          Raasta<span className="ai">AI</span> <span className="tag">Admin</span>
        </div>
        <nav>
          {(['overview', 'reports', 'hotspots'] as Tab[]).map((t) => (
            <button key={t} className={tab === t ? 'nav on' : 'nav'} onClick={() => {
                setFocus(null)
                setTab(t)
              }}>
              {t[0].toUpperCase() + t.slice(1)}
            </button>
          ))}
        </nav>
        <div className="spacer" />
        <span className="chip">Pilot concept</span>
        <span className="muted small">{user.email}</span>
        <button className="link" onClick={() => signOut(auth)}>
          Sign out
        </button>
      </header>
      {error && <div className="alert err">{error}</div>}
      {reports && reports.length >= MAX_REPORTS && <div className="alert warn">Showing the newest {MAX_REPORTS} reports.</div>}
      <main className="page">
        {reports === null ? (
          <div className="center muted">Loading reports…</div>
        ) : tab === 'overview' ? (
          <Overview reports={reports} clusters={clusters} onOpenCluster={openCluster} />
        ) : tab === 'reports' ? (
          <Reports key={focus?.clusterId ?? 'all'} reports={reports} clusters={clusters} focus={focus} />
        ) : (
          <Hotspots clusters={clusters} onOpenCluster={openCluster} />
        )}
      </main>
    </div>
  )
}
