export interface QRInfo {
  token: string
  original_url: string
  created_at: string
  updated_at: string
  expires_at: string | null
  is_deleted: boolean
}

export type Status = 'active' | 'expired' | 'deleted'

export function deriveStatus(info: QRInfo | null): Status {
  if (!info) return 'active'
  if (info.is_deleted) return 'deleted'
  if (info.expires_at && new Date(info.expires_at) < new Date()) return 'expired'
  return 'active'
}

export function fmtDate(s: string): string {
  return new Date(s).toLocaleString('zh-TW', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}
