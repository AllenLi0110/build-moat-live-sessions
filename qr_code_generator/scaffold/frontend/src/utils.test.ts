import { describe, it, expect } from 'vitest'
import { deriveStatus, fmtDate } from './utils'
import type { QRInfo } from './utils'

const base: QRInfo = {
  token: 'abc1234',
  original_url: 'https://example.com',
  created_at: '2024-01-01T00:00:00',
  updated_at: '2024-01-01T00:00:00',
  expires_at: null,
  is_deleted: false,
}

describe('deriveStatus', () => {
  it('returns active for a live, non-expired mapping', () => {
    expect(deriveStatus(base)).toBe('active')
  })

  it('returns active when info is null (no QR generated yet)', () => {
    expect(deriveStatus(null)).toBe('active')
  })

  it('returns deleted when is_deleted is true', () => {
    expect(deriveStatus({ ...base, is_deleted: true })).toBe('deleted')
  })

  it('deleted takes priority over expired', () => {
    expect(deriveStatus({ ...base, is_deleted: true, expires_at: '2020-01-01T00:00:00' })).toBe('deleted')
  })

  it('returns expired when expires_at is in the past', () => {
    expect(deriveStatus({ ...base, expires_at: '2020-01-01T00:00:00' })).toBe('expired')
  })

  it('returns active when expires_at is in the future', () => {
    const future = new Date(Date.now() + 60_000).toISOString()
    expect(deriveStatus({ ...base, expires_at: future })).toBe('active')
  })

  it('returns active when expires_at is null and not deleted', () => {
    expect(deriveStatus({ ...base, expires_at: null, is_deleted: false })).toBe('active')
  })
})

describe('fmtDate', () => {
  it('returns a non-empty string for a valid ISO date string', () => {
    expect(fmtDate('2024-06-15T10:30:00')).toBeTruthy()
  })

  it('does not throw for any valid ISO string', () => {
    expect(() => fmtDate('2099-12-31T23:59:59')).not.toThrow()
  })
})
