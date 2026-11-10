// Calls to the RaastaAI API (status changes and photos go through the server, which checks the
// admin claim itself: the dashboard hiding a button is never the protection).
import { doc, getDoc } from 'firebase/firestore'
import { auth, db } from './firebase'
import type { Status } from './types'

// The API address is read at runtime from the public Firestore doc `public/config` (written by
// tools/serve_public.py when the tunnel starts). VITE_API_BASE pins it for local development.
const PINNED: string | undefined = import.meta.env.VITE_API_BASE
let resolved: string | null = null

async function apiBase(): Promise<string> {
  if (PINNED) return PINNED
  if (resolved) return resolved
  try {
    const v = (await getDoc(doc(db, 'public', 'config'))).get('apiBase')
    if (typeof v === 'string' && v.startsWith('http')) return (resolved = v.replace(/\/+$/, ''))
  } catch {
    /* fall through */
  }
  return 'http://localhost:7860'
}

export class ApiError extends Error {
  status: number
  code: string
  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

async function authHeader(): Promise<Record<string, string>> {
  const u = auth.currentUser
  if (!u) throw new ApiError(401, 'unauthenticated', 'Please sign in again.')
  return { Authorization: `Bearer ${await u.getIdToken()}` }
}

async function call(path: string, init: RequestInit = {}): Promise<Response> {
  let res: Response
  try {
    res = await fetch(`${await apiBase()}${path}`, { ...init, headers: { ...(init.headers ?? {}), ...(await authHeader()) } })
  } catch {
    resolved = null // tunnel may have restarted: re-read the address next time
    throw new ApiError(0, 'network', 'Could not reach the RaastaAI API. Is the server laptop on? Try again in a few seconds.')
  }
  if (!res.ok) {
    let body: { error?: string; message?: string } = {}
    try {
      body = await res.json()
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, body.error ?? `http_${res.status}`, body.message ?? `Request failed (${res.status}).`)
  }
  return res
}

export async function setStatus(reportId: string, status: Status) {
  const res = await call(`/admin/reports/${encodeURIComponent(reportId)}/status`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  })
  return (await res.json()) as { reportId: string; status: Status; previous: Status; changed: boolean }
}

export async function imageUrl(reportId: string): Promise<string> {
  const res = await call(`/admin/reports/${encodeURIComponent(reportId)}/image`)
  return URL.createObjectURL(await res.blob())
}
