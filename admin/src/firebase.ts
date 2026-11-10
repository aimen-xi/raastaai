import { initializeApp } from 'firebase/app'
import { getAuth } from 'firebase/auth'
import { collection, getFirestore, limit, onSnapshot, orderBy, query, Timestamp } from 'firebase/firestore'
import type { Cluster, Report } from './types'

// Public web config (not secret). Data access is enforced by Firestore rules: only accounts
// with the `admin` custom claim can read reports/clusters; nobody can write from the browser.
const app = initializeApp({
  apiKey: 'AIzaSyC0J8U-rJTaQIxPgxyNsFAuqJ9ikHN_Iyo',
  authDomain: 'rastaai-e99f8.firebaseapp.com',
  projectId: 'rastaai-e99f8',
  appId: '1:1046611325526:web:687e00e46f936b61d481f7',
  messagingSenderId: '1046611325526',
})

export const auth = getAuth(app)
export const db = getFirestore(app)

const toDate = (v: unknown): Date => (v instanceof Timestamp ? v.toDate() : v ? new Date(String(v)) : new Date(0))

export const MAX_REPORTS = 1000 // pilot scale; keeps the free-tier read quota safe

export function watchReports(cb: (r: Report[]) => void, onError: (e: Error) => void) {
  const q = query(collection(db, 'reports'), orderBy('createdAt', 'desc'), limit(MAX_REPORTS))
  return onSnapshot(
    q,
    (snap) =>
      cb(
        snap.docs.map((d) => {
          const x = d.data()
          return {
            ...(x as Omit<Report, 'id' | 'createdAt' | 'statusHistory'>),
            id: d.id,
            createdAt: toDate(x.createdAt),
            statusHistory: ((x.statusHistory as Array<Record<string, unknown>>) ?? []).map((h) => ({ ...h, at: toDate(h.at) })) as Report['statusHistory'],
          }
        }),
      ),
    onError,
  )
}

export function watchClusters(cb: (c: Cluster[]) => void, onError: (e: Error) => void) {
  return onSnapshot(
    collection(db, 'clusters'),
    (snap) =>
      cb(
        snap.docs.map((d) => {
          const x = d.data()
          return { ...(x as Omit<Cluster, 'id' | 'firstAt' | 'lastAt'>), id: d.id, firstAt: toDate(x.firstAt), lastAt: toDate(x.lastAt) }
        }),
      ),
    onError,
  )
}
