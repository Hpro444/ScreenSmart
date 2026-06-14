import React, { useCallback, useEffect, useRef, useState } from 'react'
import Background from './Background.jsx'
import { feed } from './feed.js'
import { getReview } from './api.js'

export default function App() {
  const [view, setView] = useState('landing')
  useEffect(() => { feed.start() }, [])
  return view === 'landing'
    ? <Landing onEnter={() => setView('review')} />
    : <Review onBack={() => setView('landing')} />
}

// shared live counts / connection state
function useMeta() {
  const [meta, setMeta] = useState({ counts: feed.counts, connected: feed.connected })
  useEffect(() => feed.onMeta(setMeta), [])
  return meta
}

/* ----------------------------- landing ----------------------------- */
function Landing({ onEnter }) {
  const { counts, connected } = useMeta()
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onEnter() }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onEnter])

  return (
    <main className="landing" onClick={onEnter} role="button" tabIndex={0}
          aria-label="Open the review desk">
      <Background intensity={1} ambient={0} />
      <div className="landing-scrim" />

      <header className="top-bar">
        <div className="brand-mini"><span className="mark">◈</span> ScreenSmart</div>
        <LiveBadge connected={connected} />
      </header>

      <div className="hero">
        <h1 className="hero-title">Screen<span>Smart</span></h1>
        <p className="hero-tagline">Real-time sanctions screening — every payment, sub-second.</p>
        <button className="enter-cta" onClick={(e) => { e.stopPropagation(); onEnter() }}>
          <span className="pulse" /> Open the review desk
          <span className="kbd-hint">click anywhere · <kbd>Enter</kbd></span>
        </button>
      </div>

      <footer className="landing-foot" onClick={(e) => e.stopPropagation()}>
        <div className="stats">
          <Stat label="Cleared" n={counts.allowed} cls="ok" />
          <Stat label="In review" n={counts.review} cls="rev" />
          <Stat label="Blocked" n={counts.blocked} cls="blk" />
        </div>
        <div className="legend">
          <span><i className="lg ok" /> cleared — flows through</span>
          <span><i className="lg rev" /> review — lifts up</span>
          <span><i className="lg blk" /> blocked — drops out</span>
        </div>
      </footer>
    </main>
  )
}

function Stat({ label, n, cls }) {
  return (
    <div className={'stat ' + cls}>
      <div className="stat-n">{Number(n).toLocaleString()}</div>
      <div className="stat-l">{label}</div>
    </div>
  )
}

function LiveBadge({ connected }) {
  return (
    <span className={'live-badge ' + (connected ? 'on' : 'off')}>
      <span className="ping" />{connected ? 'LIVE' : 'offline'}
    </span>
  )
}

/* ----------------------------- review desk ----------------------------- */
function Review({ onBack }) {
  const { counts, connected } = useMeta()
  const [items, setItems] = useState([])
  const [sel, setSel] = useState(null)
  const [err, setErr] = useState('')
  const [loading, setLoading] = useState(true)
  const debounce = useRef(null)

  const load = useCallback(() => {
    getReview()
      .then((d) => { setItems(d); setErr('') })
      .catch(() => setErr('Could not reach the review queue.'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  // keep the queue fresh as new review verdicts stream in (debounced)
  useEffect(() => feed.onVerdict((v) => {
    if (v.status === 'review') { clearTimeout(debounce.current); debounce.current = setTimeout(load, 900) }
  }), [load])

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onBack() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onBack])

  return (
    <main className="review">
      <div className="review-bg"><Background intensity={0.55} ambient={0} /></div>
      <div className="review-scrim" />

      <header className="rev-head">
        <button className="back" onClick={onBack}>← Live view</button>
        <div className="rev-title"><span className="mark">◈</span> Review Desk</div>
        <div className="rev-right">
          <span className="chip ok">{counts.allowed.toLocaleString()} cleared</span>
          <span className="chip rev">{counts.review.toLocaleString()} review</span>
          <span className="chip blk">{counts.blocked.toLocaleString()} blocked</span>
          <LiveBadge connected={connected} />
        </div>
      </header>

      <div className="rev-body">
        <aside className="queue">
          <div className="queue-head">Flagged for review <span className="badge">{items.length}</span></div>
          {loading && <div className="muted pad">Loading queue…</div>}
          {err && <div className="err pad">{err}</div>}
          {!loading && !err && items.length === 0 &&
            <div className="muted pad">Queue is clear — nothing awaiting review.</div>}
          <div className="queue-list">
            {items.map((d) => (
              <QueueItem key={d.txn_id} d={d} active={sel?.txn_id === d.txn_id} onClick={() => setSel(d)} />
            ))}
          </div>
        </aside>

        <section className="detail">
          {sel ? <Dossier d={sel} /> : <EmptyDetail />}
        </section>
      </div>
    </main>
  )
}

function QueueItem({ d, active, onClick }) {
  const t = d.txn || {}
  const who = t.bene_name || t.wallet || d.txn_id
  const meta = [t.bene_country, t.channel].filter(Boolean).join(' · ')
  return (
    <button className={'qitem' + (active ? ' active' : '')} onClick={onClick}>
      <span className="qdot rev" />
      <span className="qtext">
        <span className="qname">{who}</span>
        <span className="qmeta">{meta || '—'}</span>
      </span>
      {t.amount != null && <span className="qamt">{fmtAmount(t.amount, t.currency)}</span>}
    </button>
  )
}

function EmptyDetail() {
  return (
    <div className="empty">
      <div className="empty-mark">◈</div>
      <h3>Select a flagged payment</h3>
      <p>Pick an item from the queue to see the full dossier — both screening modules,
        the original payment, and exactly why it was flagged.</p>
    </div>
  )
}

function Dossier({ d }) {
  const t = d.txn || {}
  return (
    <div className="dossier">
      <div className="dossier-head">
        <h2>{t.bene_name || t.wallet || d.txn_id}</h2>
        <span className={'pill ' + statusClass(d.combined_verdict)}>{d.combined_verdict}</span>
      </div>
      <div className="grid">
        <Field k="Txn ID" v={d.txn_id} />
        <Field k="Channel" v={t.channel} />
        <Field k="Amount" v={t.amount != null ? fmtAmount(t.amount, t.currency) : '—'} />
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
      {d.reasons?.length > 0 && (
        <>
          <h3 className="section">Why it was flagged</h3>
          <ul className="reasons">{d.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>
        </>
      )}
    </div>
  )
}

function ModuleCard({ title, r }) {
  if (!r || !r.applicable) return <div className="module na">{title} · <em>not applicable</em></div>
  return (
    <div className="module">
      <div className="module-head">
        <h4>{title}</h4>
        <span className={'pill ' + verdictClass(r.verdict)}>{r.verdict}</span>
      </div>
      <div className="grid tight">
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

/* ----------------------------- helpers ----------------------------- */
function statusClass(verdict) {
  return verdict === 'MATCH' ? 'blk' : verdict === 'REVIEW' ? 'rev' : 'ok'
}
function verdictClass(verdict) {
  return verdict === 'MATCH' ? 'blk' : verdict === 'REVIEW' ? 'rev' : 'ok'
}
function fmtAmount(amount, currency) {
  const n = Number(amount)
  const s = Number.isFinite(n) ? n.toLocaleString(undefined, { maximumFractionDigits: 2 }) : amount
  return currency ? `${s} ${currency}` : `${s}`
}
