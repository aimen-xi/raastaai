import { describe, expect, it } from 'vitest'
import { aiSummary, applyFilters, hotspotAreas, inPeriod, isActiveHotspot, kpis, NO_FILTERS, timeAgo } from './logic'
import type { Cluster, Report } from './types'

const now = new Date('2026-11-10T12:00:00Z')
const r = (over: Partial<Report>): Report => ({
  id: 'RA-AAAAAA', category: 'pothole', lat: 31.5, lng: 74.3, accuracyM: 10, locationSource: 'gps', outsidePakistan: false,
  status: 'pending', statusHistory: [], clusterId: 'C-AAAAAA', note: '', createdAt: now, imageWidth: 1280, imageHeight: 960,
  imageBytes: 100000, aiOutcome: 'issue', aiCategory: 'pothole', aiConfidence: 0.82, userCorrected: false, userOverride: false,
  verification: 'verified', ...over,
})

describe('kpis', () => {
  it('counts categories, verification and statuses', () => {
    const k = kpis([
      r({}),
      r({ id: 'RA-B', category: 'garbage', verification: 'unverified' }),
      r({ id: 'RA-C', status: 'resolved' }),
      r({ id: 'RA-D', status: 'in_progress', verification: 'unverified' }),
    ])
    expect(k).toMatchObject({ total: 4, pothole: 3, potholeVerified: 2, garbage: 1, garbageVerified: 0, pending: 2, needsReview: 1, inProgress: 1, resolved: 1 })
  })
})

describe('filters', () => {
  const list = [r({}), r({ id: 'RA-ZZZ999', category: 'garbage', locationSource: 'manual_pin', verification: 'unverified', status: 'resolved' })]
  it('no filters returns everything', () => expect(applyFilters(list, NO_FILTERS)).toHaveLength(2))
  it('search by id is case-insensitive', () => expect(applyFilters(list, { ...NO_FILTERS, q: 'zzz' }).map((x) => x.id)).toEqual(['RA-ZZZ999']))
  it('combines filters', () => {
    expect(applyFilters(list, { ...NO_FILTERS, category: 'garbage', source: 'manual_pin', verification: 'unverified', status: 'resolved' })).toHaveLength(1)
    expect(applyFilters(list, { ...NO_FILTERS, category: 'garbage', source: 'gps' })).toHaveLength(0)
  })
  it('priority order: AI-verified, then unverified, then AI found nothing; newest first within each', () => {
    const t = (h: number) => new Date(now.getTime() - h * 3600_000)
    const mixed = [
      r({ id: 'RA-REJ', verification: 'ai_rejected', createdAt: t(0) }),
      r({ id: 'RA-UN1', verification: 'unverified', createdAt: t(1) }),
      r({ id: 'RA-VOLD', verification: 'verified', createdAt: t(5) }),
      r({ id: 'RA-VNEW', verification: 'verified', createdAt: t(2) }),
    ]
    expect(applyFilters(mixed, NO_FILTERS).map((x) => x.id)).toEqual(['RA-VNEW', 'RA-VOLD', 'RA-UN1', 'RA-REJ'])
    expect(applyFilters(mixed, { ...NO_FILTERS, sort: 'newest' }).map((x) => x.id)).toEqual(['RA-REJ', 'RA-UN1', 'RA-VNEW', 'RA-VOLD'])
    expect(applyFilters(mixed, { ...NO_FILTERS, verification: 'ai_rejected' }).map((x) => x.id)).toEqual(['RA-REJ'])
    expect(kpis(mixed).aiRejected).toBe(1)
  })
})

describe('labels and time', () => {
  it('summarises AI outcomes honestly', () => {
    expect(aiSummary(r({}))).toBe('Likely · 82%')
    expect(aiSummary(r({ aiOutcome: 'error', aiConfidence: null }))).toBe('Failed · manual')
    expect(aiSummary(r({ userCorrected: true, category: 'garbage' }))).toContain('citizen changed')
  })
  it('periods and relative times', () => {
    expect(inPeriod(new Date('2026-11-05T12:00:00Z'), '7d', now)).toBe(true)
    expect(inPeriod(new Date('2026-11-01T12:00:00Z'), '7d', now)).toBe(false)
    expect(timeAgo(new Date('2026-11-10T10:00:00Z'), now)).toBe('2 h ago')
  })
  it('nearby hotspot clusters of the same category are one area', () => {
    const base: Cluster = { id: 'C-A', category: 'pothole', centroidLat: 31.504, centroidLng: 74.3311, reportCount: 3, firstAt: now, lastAt: now, isHotspot: true, nearbyCount30d: 3 }
    const near = { ...base, id: 'C-B', centroidLat: 31.504 + 30 / 111195, reportCount: 1, nearbyCount30d: 4 }
    const otherCat = { ...base, id: 'C-C', category: 'garbage' as const }
    const far = { ...base, id: 'C-D', centroidLat: 31.6 }
    const areas = hotspotAreas([base, near, otherCat, far], now)
    expect(areas.map((a) => a.members.map((m) => m.id))).toEqual([['C-B', 'C-A'], ['C-C'], ['C-D']])
  })
  it('hotspots expire after 30 days without reports', () => {
    const c: Cluster = { id: 'C-1', category: 'pothole', centroidLat: 0, centroidLng: 0, reportCount: 3, firstAt: now, lastAt: new Date('2026-10-01T00:00:00Z'), isHotspot: true, nearbyCount30d: 3 }
    expect(isActiveHotspot(c, now)).toBe(false)
    expect(isActiveHotspot({ ...c, lastAt: now }, now)).toBe(true)
  })
})
