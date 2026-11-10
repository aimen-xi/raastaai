export type Category = 'pothole' | 'garbage'
export type Status = 'pending' | 'in_progress' | 'resolved'

export interface StatusChange {
  from: Status | null
  to: Status
  by: string
  at: Date
}

export interface Report {
  id: string
  category: Category
  lat: number
  lng: number
  accuracyM: number | null
  locationSource: 'gps' | 'manual_pin'
  outsidePakistan: boolean
  status: Status
  statusHistory: StatusChange[]
  clusterId: string
  note: string
  createdAt: Date
  imageWidth: number
  imageHeight: number
  imageBytes: number
  aiOutcome: 'issue' | 'uncertain' | 'not_issue' | 'error'
  aiCategory: Category | null
  aiConfidence: number | null
  userCorrected: boolean
  userOverride: boolean
  /** verified: AI said issue + citizen agreed · unverified: AI unsure/unavailable or category changed ·
   *  ai_rejected: AI found nothing, citizen reported anyway with a note (lowest priority, never a hotspot) */
  verification: Verification
  aiReason?: string | null
  aiCheckedBy?: 'client' | 'server' | null
  /** Same picture (exact or visually) already used by another citizen within 25 m: that report's ID */
  photoReusedFrom?: string | null
  /** One of the app's bundled staged demo photos */
  demoSample?: boolean
}

export type Verification = 'verified' | 'unverified' | 'ai_rejected'

export interface Cluster {
  id: string
  category: Category
  centroidLat: number
  centroidLng: number
  reportCount: number
  firstAt: Date
  lastAt: Date
  isHotspot: boolean
  nearbyCount30d: number
}
