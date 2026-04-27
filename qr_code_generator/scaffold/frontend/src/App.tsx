import { useState, useEffect } from 'react'

interface CreateResponse {
  token: string
  short_url: string
  qr_code_url: string
  original_url: string
}

interface QRInfo {
  token: string
  original_url: string
  created_at: string
  updated_at: string
  expires_at: string | null
  is_deleted: boolean
}

interface Analytics {
  token: string
  total_scans: number
  scans_by_day: { date: string; count: number }[]
}

// ── Design tokens ────────────────────────────────────────────────
const C = {
  bg:        '#0d1117',
  surface:   '#161b22',
  border:    '#30363d',
  green:     '#39d353',
  blue:      '#58a6ff',
  red:       '#f85149',
  amber:     '#d29922',
  text:      '#e6edf3',
  muted:     '#8b949e',
}

const STATUS_COLOR  = { active: C.green, expired: C.amber, deleted: C.red }
const STATUS_LABEL  = { active: 'Active', expired: 'Expired', deleted: 'Deleted' }

// ── Reusable micro-components ─────────────────────────────────────
function GhostBtn({
  color = C.green, onClick, disabled, children,
}: {
  color?: string; onClick: () => void; disabled?: boolean; children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        padding: '5px 14px',
        background: 'transparent',
        color: disabled ? C.muted : color,
        border: `1px solid ${disabled ? C.border : color}`,
        borderRadius: 4,
        cursor: disabled ? 'default' : 'pointer',
        fontFamily: 'system-ui, sans-serif',
        fontSize: 16,
        fontWeight: 600,
        letterSpacing: '0.02em',
        transition: 'opacity 0.15s',
        opacity: disabled ? 0.4 : 1,
      }}
    >
      {children}
    </button>
  )
}

function StatusBadge({ status }: { status: 'active' | 'expired' | 'deleted' }) {
  return (
    <span style={{
      color: STATUS_COLOR[status],
      border: `1px solid ${STATUS_COLOR[status]}`,
      padding: '2px 10px',
      borderRadius: 999,
      fontSize: 16,
      fontWeight: 700,
      letterSpacing: '0.05em',
      textTransform: 'uppercase',
    }}>
      ● {STATUS_LABEL[status]}
    </span>
  )
}

function Label({ children }: { children: React.ReactNode }) {
  return <span style={{ color: C.muted, fontSize: 16, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', minWidth: 64, flexShrink: 0 }}>{children}</span>
}

function Mono({ children, color }: { children: React.ReactNode; color?: string }) {
  return <span style={{ fontFamily: "'JetBrains Mono', 'Fira Code', monospace", fontSize: 16, color: color ?? C.text, wordBreak: 'break-all' }}>{children}</span>
}

function Divider() {
  return <div style={{ borderTop: `1px solid ${C.border}`, margin: '0' }} />
}

// ── App ───────────────────────────────────────────────────────────
export default function App() {
  const [url, setUrl]                   = useState('')
  const [loading, setLoading]           = useState(false)
  const [error, setError]               = useState('')
  const [qrData, setQrData]             = useState<CreateResponse | null>(null)
  const [info, setInfo]                 = useState<QRInfo | null>(null)
  const [updateUrl, setUpdateUrl]       = useState('')
  const [analytics, setAnalytics]       = useState<Analytics | null>(null)
  const [redirectStatus, setRedirectStatus] = useState<number | null>(null)
  const [countdown, setCountdown]       = useState<number | null>(null)

  const status: 'active' | 'expired' | 'deleted' =
    info?.is_deleted ? 'deleted'
    : info?.expires_at && new Date(info.expires_at) < new Date() ? 'expired'
    : 'active'

  useEffect(() => {
    if (!info?.expires_at || info.is_deleted) { setCountdown(null); return }
    const tick = () => setCountdown(Math.max(0, Math.floor((new Date(info.expires_at!).getTime() - Date.now()) / 1000)))
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [info?.expires_at, info?.is_deleted])

  const fetchInfo = async (token: string) => {
    const res = await fetch(`/api/qr/${token}`)
    if (res.ok) setInfo(await res.json())
  }

  const handleGenerate = async () => {
    if (!url) return
    setLoading(true); setError(''); setQrData(null); setInfo(null); setAnalytics(null); setRedirectStatus(null)
    try {
      const res = await fetch('/api/qr/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail ?? 'Failed')
      setQrData(data)
      await fetchInfo(data.token)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  const handleUpdate = async () => {
    if (!qrData) return
    const body: Record<string, string> = { expires_at: new Date(Date.now() + 60_000).toISOString() }
    if (updateUrl) body.url = updateUrl
    const res = await fetch(`/api/qr/${qrData.token}`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    })
    if (res.ok) {
      setInfo(await res.json())
      if (updateUrl) setQrData(p => p ? { ...p, original_url: updateUrl } : p)
    }
  }

  const handleDelete = async () => {
    if (!qrData) return
    await fetch(`/api/qr/${qrData.token}`, { method: 'DELETE' })
    setInfo(p => p ? { ...p, is_deleted: true } : p)
  }

  const handleAnalytics = async () => {
    if (!qrData) return
    const res = await fetch(`/api/qr/${qrData.token}/analytics`)
    if (res.ok) setAnalytics(await res.json())
  }

  const handleTestRedirect = async () => {
    if (!qrData) return
    const res = await fetch(`/api/qr/${qrData.token}/check`)
    if (res.ok) {
      const data = await res.json()
      setRedirectStatus(data.status)
    }
  }

  const fmtDate = (s: string) =>
    new Date(s).toLocaleString('zh-TW', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })

  const redirectStatusColor =
    redirectStatus === 302 ? C.green
    : redirectStatus === 410 ? C.red
    : redirectStatus === 404 ? C.amber
    : C.muted

  return (
    <div style={{ minHeight: '100vh', background: C.bg, color: C.text, fontFamily: 'system-ui, sans-serif' }}>
      <div style={{ maxWidth: 860, margin: '0 auto', padding: '28px 24px' }}>

        {/* Row 1 — Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <div>
            <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 18, color: C.green, marginRight: 8 }}>$</span>
            <span style={{ fontSize: 16, fontWeight: 700, letterSpacing: '0.02em' }}>qr-generator</span>
            <span style={{ color: C.muted, fontSize: 16, marginLeft: 10 }}>— dynamic link manager</span>
          </div>
          {info && <StatusBadge status={status} />}
        </div>

        {/* Row 2 — Input bar */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 4 }}>
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', background: C.surface, border: `1px solid ${C.border}`, borderRadius: 4, paddingLeft: 10 }}>
            <span style={{ color: C.muted, fontFamily: 'monospace', fontSize: 16, marginRight: 6 }}>url:</span>
            <input
              value={url}
              onChange={e => setUrl(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleGenerate()}
              placeholder="https://example.com"
              style={{ flex: 1, background: 'transparent', border: 'none', outline: 'none', color: C.text, fontFamily: "'JetBrains Mono', monospace", fontSize: 16, padding: '8px 0' }}
            />
          </div>
          <GhostBtn onClick={handleGenerate} disabled={loading || !url} color={C.green}>
            {loading ? 'generating…' : '⏎ generate'}
          </GhostBtn>
        </div>
        {error && (
          <div style={{ color: C.red, fontSize: 16, fontFamily: 'monospace', marginBottom: 8, paddingLeft: 2 }}>
            ✗ {error}
          </div>
        )}

        {qrData && info && (
          <div style={{ border: `1px solid ${C.border}`, borderRadius: 6, overflow: 'hidden', marginTop: 16 }}>

            {/* Row 3 — QR + info */}
            <div style={{ display: 'grid', gridTemplateColumns: '196px 1fr' }}>
              {/* QR image */}
              <div style={{ background: '#ffffff', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 12, borderRight: `1px solid ${C.border}` }}>
                <img src={qrData.qr_code_url} alt="QR Code" style={{ width: 172, height: 172, display: 'block' }} />
              </div>

              {/* Info */}
              <div>
                {/* Token / URL rows */}
                <div style={{ padding: '12px 16px' }}>
                  {[
                    { label: 'token',  val: <Mono color={C.green}>{qrData.token}</Mono> },
                    { label: 'short',  val: <a href={qrData.short_url} target="_blank" rel="noreferrer" style={{ color: C.blue, fontFamily: 'monospace', fontSize: 16, textDecoration: 'none' }}>{qrData.short_url}</a> },
                    { label: 'target', val: <Mono color={C.muted}>{info.original_url}</Mono> },
                  ].map(({ label, val }) => (
                    <div key={label} style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 6 }}>
                      <Label>{label}</Label>
                      {val}
                    </div>
                  ))}
                </div>

                <Divider />

                {/* Metadata grid */}
                <div style={{ padding: '10px 16px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px 24px' }}>
                  {[
                    { label: 'created', val: fmtDate(info.created_at) },
                    { label: 'updated', val: fmtDate(info.updated_at) },
                    { label: 'expires', val: info.expires_at ? fmtDate(info.expires_at) : '—' },
                    { label: 'deleted', val: info.is_deleted ? <span style={{ color: C.red }}>yes</span> : 'no' },
                  ].map(({ label, val }) => (
                    <div key={label} style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                      <Label>{label}</Label>
                      <span style={{ fontSize: 16, color: C.text }}>{val}</span>
                    </div>
                  ))}
                  {countdown !== null && countdown > 0 && (
                    <div style={{ gridColumn: '1 / -1', fontFamily: 'monospace', fontSize: 16, color: countdown < 10 ? C.red : C.amber, marginTop: 2 }}>
                      ⏱ expires in {countdown}s
                    </div>
                  )}
                </div>
              </div>
            </div>

            <Divider />

            {/* Row 4 — Update bar */}
            {!info.is_deleted && (
              <>
                <div style={{ display: 'flex', gap: 8, padding: '10px 12px', alignItems: 'center' }}>
                  <span style={{ color: C.muted, fontFamily: 'monospace', fontSize: 16, whiteSpace: 'nowrap' }}>new url:</span>
                  <input
                    value={updateUrl}
                    onChange={e => setUpdateUrl(e.target.value)}
                    placeholder="leave blank to keep current target"
                    style={{ flex: 1, background: 'transparent', border: 'none', borderBottom: `1px solid ${C.border}`, outline: 'none', color: C.text, fontFamily: 'monospace', fontSize: 16, padding: '4px 0' }}
                  />
                  <GhostBtn onClick={handleUpdate} color={C.blue}>PATCH +1 min</GhostBtn>
                </div>
                <Divider />
              </>
            )}

            {/* Deleted banner */}
            {info.is_deleted && (
              <>
                <div style={{ padding: '8px 16px', fontFamily: 'monospace', fontSize: 16, color: C.red }}>
                  ✗ deleted — /r/{qrData.token} returns 410
                </div>
                <Divider />
              </>
            )}

            {/* Row 5 — Action bar */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 12px', flexWrap: 'wrap' }}>
              <GhostBtn color={C.muted} onClick={handleAnalytics}>analytics</GhostBtn>
              <GhostBtn color={C.muted} onClick={handleTestRedirect}>test redirect</GhostBtn>
              {!info.is_deleted && <GhostBtn color={C.red} onClick={handleDelete}>delete</GhostBtn>}
              {redirectStatus !== null && (
                <span style={{ marginLeft: 4, fontFamily: 'monospace', fontSize: 16, color: redirectStatusColor }}>
                  → {redirectStatus}
                </span>
              )}
            </div>

            {/* Row 6 — Analytics */}
            {analytics && (
              <>
                <Divider />
                <div style={{ padding: '10px 16px', fontSize: 16 }}>
                  <span style={{ color: C.muted, fontFamily: 'monospace', marginRight: 16 }}>total scans</span>
                  <span style={{ color: C.green, fontFamily: 'monospace', fontWeight: 700 }}>{analytics.total_scans}</span>
                  {analytics.scans_by_day.length > 0 && (
                    <span style={{ marginLeft: 24 }}>
                      {analytics.scans_by_day.map(r => (
                        <span key={r.date} style={{ fontFamily: 'monospace', color: C.muted, marginRight: 16 }}>
                          {r.date} <span style={{ color: C.text }}>{r.count}</span>
                        </span>
                      ))}
                    </span>
                  )}
                  {analytics.scans_by_day.length === 0 && (
                    <span style={{ color: C.muted, fontFamily: 'monospace', marginLeft: 16 }}>— no scans yet</span>
                  )}
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
