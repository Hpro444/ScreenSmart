// API + WebSocket endpoints (override at build time with VITE_API_URL / VITE_WS_URL).
export const API = import.meta.env.VITE_API_URL || 'http://localhost:8091'
export const WS = import.meta.env.VITE_WS_URL || 'ws://localhost:8091/ws/feed'

// The review desk needs a bearer token, but we don't want a login screen. We silently
// authenticate with the demo analyst account and cache the token. Creds are overridable
// at build time so this still works against a hardened gateway.
const ANALYST = {
  user: import.meta.env.VITE_ANALYST_USER || 'analyst',
  pass: import.meta.env.VITE_ANALYST_PASSWORD || 'analyst',
}

let _tokenPromise = null

export async function ensureToken(force = false) {
  if (force) { localStorage.removeItem('ss_token'); _tokenPromise = null }
  const cached = localStorage.getItem('ss_token')
  if (cached && !force) return cached
  if (!_tokenPromise) {
    _tokenPromise = fetch(`${API}/auth/login`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: ANALYST.user, password: ANALYST.pass }),
    })
      .then((r) => { if (!r.ok) throw new Error('auth failed'); return r.json() })
      .then((j) => { localStorage.setItem('ss_token', j.token); _tokenPromise = null; return j.token })
      .catch((e) => { _tokenPromise = null; throw e })
  }
  return _tokenPromise
}

export async function getStats() {
  try {
    const r = await fetch(`${API}/stats`)
    return r.ok ? r.json() : { allowed: 0, review: 0, blocked: 0 }
  } catch { return { allowed: 0, review: 0, blocked: 0 } }
}

export async function getReview(limit = 200) {
  let token = await ensureToken()
  let r = await fetch(`${API}/review?limit=${limit}`, { headers: { Authorization: `Bearer ${token}` } })
  if (r.status === 401) {                       // token expired → re-auth once
    token = await ensureToken(true)
    r = await fetch(`${API}/review?limit=${limit}`, { headers: { Authorization: `Bearer ${token}` } })
  }
  if (!r.ok) throw new Error('review unavailable')
  return r.json()
}
