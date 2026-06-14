// A single shared live feed. One WebSocket to the ws-gateway, fanned out to every
// subscriber (the background animation + the counters + the review desk), so switching
// views never opens a second socket or loses the running counts.
import { API, WS } from './api.js'

class Feed {
  constructor() {
    this.counts = { allowed: 0, review: 0, blocked: 0 }
    this.connected = false
    this.verdictSubs = new Set()   // (verdict) => void
    this.metaSubs = new Set()      // ({counts, connected}) => void
    this.ws = null
    this._retryTimer = null
    this._started = false
  }

  start() {
    if (this._started) return
    this._started = true
    fetch(`${API}/stats`).then((r) => (r.ok ? r.json() : null)).then((s) => {
      if (s) { this.counts = { allowed: s.allowed || 0, review: s.review || 0, blocked: s.blocked || 0 }; this._emitMeta() }
    }).catch(() => {})
    this._connect()
  }

  _connect() {
    try { this.ws = new WebSocket(WS) } catch { this._scheduleRetry(); return }
    this.ws.onopen = () => { this.connected = true; this._emitMeta() }
    this.ws.onerror = () => { try { this.ws.close() } catch { /* ignore */ } }
    this.ws.onclose = () => { this.connected = false; this.ws = null; this._emitMeta(); this._scheduleRetry() }
    this.ws.onmessage = (e) => {
      let v
      try { v = JSON.parse(e.data) } catch { return }
      const status = v.status || 'allowed'
      this.counts = { ...this.counts, [status]: (this.counts[status] || 0) + 1 }
      this._emitMeta()
      this.verdictSubs.forEach((cb) => { try { cb(v) } catch { /* ignore */ } })
    }
  }

  _scheduleRetry() {
    clearTimeout(this._retryTimer)
    this._retryTimer = setTimeout(() => this._connect(), 1500)
  }

  onVerdict(cb) { this.verdictSubs.add(cb); return () => this.verdictSubs.delete(cb) }

  onMeta(cb) {
    this.metaSubs.add(cb)
    cb(this._meta())
    return () => this.metaSubs.delete(cb)
  }

  _meta() { return { counts: this.counts, connected: this.connected } }
  _emitMeta() { const m = this._meta(); this.metaSubs.forEach((cb) => { try { cb(m) } catch { /* ignore */ } }) }
}

export const feed = new Feed()
