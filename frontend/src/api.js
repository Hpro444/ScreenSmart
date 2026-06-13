// API + WebSocket endpoints (override at build time with VITE_API_URL / VITE_WS_URL)
export const API = import.meta.env.VITE_API_URL || 'http://localhost:8091'
export const WS = import.meta.env.VITE_WS_URL || 'ws://localhost:8091/ws/feed'

export async function login(username, password) {
  const r = await fetch(`${API}/auth/login`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  if (!r.ok) throw new Error('invalid credentials')
  return r.json()
}

export async function getStats() {
  const r = await fetch(`${API}/stats`)
  return r.ok ? r.json() : { allowed: 0, review: 0, blocked: 0 }
}

export async function getReview(token) {
  const r = await fetch(`${API}/review`, { headers: { Authorization: `Bearer ${token}` } })
  if (!r.ok) throw new Error('unauthorized')
  return r.json()
}
