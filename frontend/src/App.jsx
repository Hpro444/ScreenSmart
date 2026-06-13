import React, { useEffect, useRef, useState } from 'react'
import { WS, getStats, login, getReview } from './api.js'

const STATUS_COLOR = { allowed: '#21c06b', review: '#e8b923', blocked: '#e5484d' }
const MAX_DOTS = 720

export default function App() {
  const [view, setView] = useState('landing')
  const [token, setToken] = useState(localStorage.getItem('ss_token') || '')

  return (
    <div className="app">
      <header>
        <h1>🛡️ ScreenSmart <span className="sub">live sanctions screening</span></h1>
        <nav>
          <button className={view === 'landing' ? 'on' : ''} onClick={() => setView('landing')}>Live feed</button>
          <button className={view === 'review' ? 'on' : ''} onClick={() => setView(token ? 'review' : 'login')}>
            Review queue
          </button>
          {token && <button onClick={() => { localStorage.removeItem('ss_token'); setToken(''); setView('landing') }}>Log out</button>}
        </nav>
      </header>

      {view === 'landing' && <Landing />}
      {view === 'login' && <Login onAuth={(t) => { setToken(t); localStorage.setItem('ss_token', t); setView('review') }} />}
      {view === 'review' && token && <Review token={token} />}
    </div>
  )
}

function Landing() {
  const [dots, setDots] = useState([])
  const [counts, setCounts] = useState({ allowed: 0, review: 0, blocked: 0 })
  const [connected, setConnected] = useState(false)
  const dotsRef = useRef([])

  useEffect(() => {
    getStats().then(setCounts).catch(() => {})
    const ws = new WebSocket(WS)
    ws.onopen = () => setConnected(true)
    ws.onclose = () => setConnected(false)
    ws.onmessage = (e) => {
      let v
      try { v = JSON.parse(e.data) } catch { return }
      const status = v.status || 'allowed'
      dotsRef.current = [...dotsRef.current.slice(-(MAX_DOTS - 1)), { id: v.txn_id, status, name: v.txn?.bene_name || v.txn?.wallet || '' }]
      setDots(dotsRef.current)
      setCounts((c) => ({ ...c, [status]: (c[status] || 0) + 1 }))
    }
    return () => ws.close()
  }, [])

  return (
    <main>
      <div className="counters">
        <Counter label="Allowed" n={counts.allowed} color={STATUS_COLOR.allowed} />
        <Counter label="In review" n={counts.review} color={STATUS_COLOR.review} />
        <Counter label="Blocked" n={counts.blocked} color={STATUS_COLOR.blocked} />
        <span className={'conn ' + (connected ? 'up' : 'down')}>{connected ? 'live' : 'offline'}</span>
      </div>
      <div className="wall">
        {dots.map((d, i) => (
          <span key={d.id + i} className="dot" title={`${d.status} — ${d.name}`}
                style={{ background: STATUS_COLOR[d.status] || '#888' }} />
        ))}
      </div>
      <p className="hint">Each dot is a screened payment in real time · 🟢 allowed · 🟡 in review · 🔴 blocked</p>
    </main>
  )
}

function Counter({ label, n, color }) {
  return (
    <div className="counter">
      <div className="dotbig" style={{ background: color }} />
      <div><div className="cn">{n.toLocaleString()}</div><div className="cl">{label}</div></div>
    </div>
  )
}

function Login({ onAuth }) {
  const [u, setU] = useState('analyst')
  const [p, setP] = useState('analyst')
  const [err, setErr] = useState('')
  const submit = async (e) => {
    e.preventDefault()
    try { const r = await login(u, p); onAuth(r.token) } catch { setErr('Invalid credentials') }
  }
  return (
    <main className="login">
      <form onSubmit={submit}>
        <h2>Analyst login</h2>
        <input value={u} onChange={(e) => setU(e.target.value)} placeholder="username" />
        <input type="password" value={p} onChange={(e) => setP(e.target.value)} placeholder="password" />
        <button type="submit">Sign in</button>
        {err && <p className="err">{err}</p>}
        <p className="hint">demo: analyst / analyst</p>
      </form>
    </main>
  )
}

function Review({ token }) {
  const [items, setItems] = useState([])
  const [sel, setSel] = useState(null)
  const [err, setErr] = useState('')
  useEffect(() => {
    getReview(token).then(setItems).catch(() => setErr('Session expired — log in again'))
  }, [token])

  return (
    <main className="review">
      <div className="queue">
        <h2>Review queue <span className="badge">{items.length}</span></h2>
        {err && <p className="err">{err}</p>}
        {items.map((d) => (
          <div key={d.txn_id} className={'qitem' + (sel?.txn_id === d.txn_id ? ' sel' : '')} onClick={() => setSel(d)}>
            <span className="dot" style={{ background: STATUS_COLOR.review }} />
            <span className="qname">{d.txn?.bene_name || d.txn?.wallet || d.txn_id}</span>
            <span className="qmeta">{d.txn?.bene_country || d.txn?.channel}</span>
          </div>
        ))}
      </div>
      <div className="detail">
        {!sel ? <p className="hint">Select a flagged transaction to see the full dossier.</p>
          : <Dossier d={sel} />}
      </div>
    </main>
  )
}

function Dossier({ d }) {
  const t = d.txn || {}
  return (
    <div>
      <h2>{t.bene_name || t.wallet} <span className="pill review">{d.combined_verdict}</span></h2>
      <div className="grid">
        <Field k="Txn ID" v={d.txn_id} />
        <Field k="Channel" v={t.channel} />
        <Field k="Amount" v={t.amount ? `${t.amount} ${t.currency || ''}` : '—'} />
        <Field k="Rail" v={t.rail} />
        <Field k="Sender country" v={t.orig_country} />
        <Field k="Recipient country" v={t.bene_country} />
        <Field k="DOB" v={t.bene_dob} />
        <Field k="Passport" v={t.bene_passport} />
        <Field k="National ID" v={t.bene_national_id} />
        <Field k="Wallet" v={t.wallet} />
      </div>
      <ModuleCard title="Name / identity screening" r={d.name_result} />
      <ModuleCard title="Crypto graph exposure" r={d.exposure_result} />
      <h3>Why it was flagged</h3>
      <ul className="reasons">{(d.reasons || []).map((r, i) => <li key={i}>{r}</li>)}</ul>
    </div>
  )
}

function ModuleCard({ title, r }) {
  if (!r || !r.applicable) return <div className="module na">{title}: <em>not applicable</em></div>
  return (
    <div className="module">
      <h4>{title} <span className={'pill ' + (r.verdict === 'MATCH' ? 'blocked' : r.verdict === 'REVIEW' ? 'review' : 'allowed')}>{r.verdict}</span></h4>
      <div className="grid">
        <Field k="Score" v={Number(r.score).toFixed(3)} />
        <Field k="Matched" v={r.matched_name} />
        <Field k="Entity" v={r.entity_id} />
      </div>
      {r.reasons?.length > 0 && <ul className="reasons">{r.reasons.map((x, i) => <li key={i}>{x}</li>)}</ul>}
    </div>
  )
}

function Field({ k, v }) {
  return <div className="field"><span className="fk">{k}</span><span className="fv">{v || '—'}</span></div>
}
