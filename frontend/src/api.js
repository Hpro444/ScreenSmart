// API + WebSocket endpoints (override at build time with VITE_API_URL / VITE_WS_URL).
export const API = import.meta.env.VITE_API_URL || 'http://localhost:8091'
export const WS = import.meta.env.VITE_WS_URL || 'ws://localhost:8091/ws/feed'
// local-LLM chatbot (explains why a payment was flagged)
export const CHAT = import.meta.env.VITE_CHAT_URL || 'http://localhost:8092'

// Stream the assistant's answer token-by-token. `messages` is the chat history
// [{role:'user'|'assistant', content}]; an empty history asks for the initial explanation.
export async function streamChat(dossier, messages, onToken, signal) {
  const r = await fetch(`${CHAT}/chat`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dossier, messages }), signal,
  })
  if (!r.ok || !r.body) throw new Error('chat unavailable')
  const reader = r.body.getReader()
  const dec = new TextDecoder()
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    onToken(dec.decode(value, { stream: true }))
  }
}

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

export async function decide(txnId, decision) {
  let token = await ensureToken()
  const opts = (t) => ({
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${t}` },
    body: JSON.stringify({ decision }),
  })
  let r = await fetch(`${API}/review/${encodeURIComponent(txnId)}/decision`, opts(token))
  if (r.status === 401) { token = await ensureToken(true); r = await fetch(`${API}/review/${encodeURIComponent(txnId)}/decision`, opts(token)) }
  if (!r.ok) throw new Error('decision failed')
  return r.json()
}

export async function getNode(nodeKey) {
  let token = await ensureToken()
  const url = `${API}/node/${encodeURIComponent(nodeKey)}`
  let r = await fetch(url, { headers: { Authorization: `Bearer ${token}` } })
  if (r.status === 401) { token = await ensureToken(true); r = await fetch(url, { headers: { Authorization: `Bearer ${token}` } }) }
  if (r.status === 404) return null
  if (!r.ok) throw new Error('node lookup failed')
  return r.json()
}

export async function getReview(status = 'review', limit = 200) {
  const path = `${API}/review?status=${encodeURIComponent(status)}&limit=${limit}`
  let token = await ensureToken()
  let r = await fetch(path, { headers: { Authorization: `Bearer ${token}` } })
  if (r.status === 401) {                       // token expired → re-auth once
    token = await ensureToken(true)
    r = await fetch(path, { headers: { Authorization: `Bearer ${token}` } })
  }
  if (!r.ok) throw new Error('queue unavailable')
  return r.json()
}
