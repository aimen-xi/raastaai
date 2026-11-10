import { signInWithEmailAndPassword, signOut } from 'firebase/auth'
import { useState, type FormEvent } from 'react'
import { auth } from './firebase'

export function Login({ denied }: { denied: string | null }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await signInWithEmailAndPassword(auth, email.trim(), password)
    } catch (err) {
      const code = (err as { code?: string }).code ?? ''
      setError(
        code.includes('too-many-requests')
          ? 'Too many attempts. Wait a minute and try again.'
          : code.includes('network')
            ? 'Network error. Check your connection.'
            : 'Email or password is incorrect.',
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login">
      <section className="login-hero">
        <div className="brand big">
          Raasta<span className="ai">AI</span> <span className="tag">Admin</span>
        </div>
        <h1>Review reports. Spot the hotspots.</h1>
        <p>Every report was confirmed by a citizen — the AI only suggests. Duplicates within 25 m and 7 days are already grouped for you.</p>
        <p className="foot">Pilot concept · not connected to any government authority</p>
      </section>
      <section className="login-form">
        <form onSubmit={submit} className="card">
          <h2>Sign in</h2>
          <p className="muted small">Admin accounts only. Access is granted by the project team.</p>
          {denied && (
            <div className="alert err">
              <strong>No admin access (403)</strong>
              <br />
              {denied} is signed in, but this account doesn’t have the admin role. Ask the project team to grant it.
              <br />
              <button type="button" className="link" onClick={() => signOut(auth)}>
                Use another account
              </button>
            </div>
          )}
          {error && <div className="alert err">{error}</div>}
          <label>
            Email
            <input type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
          <label>
            Password
            <input type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
          </label>
          <button className="btn primary" disabled={busy}>
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </section>
    </div>
  )
}
