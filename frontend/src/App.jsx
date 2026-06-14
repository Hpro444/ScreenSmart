import React, { useCallback, useEffect, useRef, useState } from 'react'
import Background from './Background.jsx'
import { feed } from './feed.js'
import { getReview } from './api.js'

const REDUCE = typeof window !== 'undefined' && window.matchMedia
  && window.matchMedia('(prefers-reduced-motion: reduce)').matches

export default function App() {
  const [view, setView] = useState('landing')
  const [dir, setDir] = useState('fwd')
  const [anim, setAnim] = useState(false)       // curtain sweeping
  const [entering, setEntering] = useState(false) // incoming view's fade-in (only after swap)
  const busy = useRef(false)
  useEffect(() => { feed.start() }, [])

  const go = useCallback((target) => {
    if (busy.current || target === view) return
    if (REDUCE) { setView(target); return }
    busy.current = true
    setDir(target === 'review' ? 'fwd' : 'back')
    setAnim(true)                                          // one compositor keyframe sweeps in→hold→out
    setTimeout(() => { setView(target); setEntering(true) }, 320)  // swap while fully covered
    setTimeout(() => { setAnim(false); setEntering(false); busy.current = false }, 660)
  }, [view])

  return (
    <div className="stage">
      <div className={'view' + (entering ? ' enter ' + dir : '')} key={view}>
        {view === 'landing'
          ? <Landing onEnter={() => go('review')} />
          : <Review onBack={() => go('landing')} />}
      </div>
      <div className={'curtain' + (anim ? ' on ' + dir : '')} aria-hidden="true">
        <span className="curtain-mark">◈</span>
      </div>
    </div>
  )
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
  const [picked, setPicked] = useState(null)
  useEffect(() => {
    const onKey = (e) => {
      if (picked) return
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onEnter() }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onEnter, picked])

  return (
    <main className="landing" onClick={onEnter} role="button" tabIndex={0}
          aria-label="Open the review desk">
      <Background intensity={1} ambient={0} onPick={setPicked} />
      <div className="landing-scrim" />
      {picked && <TxnModal d={picked} onClose={() => setPicked(null)} />}

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

function Kpi({ n, label, cls, active, onClick }) {
  return (
    <button className={'kpi ' + cls + (active ? ' active' : '')} onClick={onClick} type="button">
      <div className="kpi-n">{Number(n).toLocaleString()}</div>
      <div className="kpi-l">{label}</div>
    </button>
  )
}

const TABS = {
  review: { title: 'In review', sev: 'rev', label: 'REVIEW', empty: 'Queue is clear — nothing awaiting review.' },
  allowed: { title: 'Cleared', sev: 'ok', label: 'CLEARED', empty: 'No cleared payments yet.' },
  blocked: { title: 'Blocked', sev: 'blk', label: 'BLOCKED', empty: 'No blocked payments yet.' },
}
const hasGraph = (d) => !!(d?.exposure_result?.detail?.graph?.nodes?.length)

/* ----------------------------- review desk ----------------------------- */
function Review({ onBack }) {
  const { counts, connected } = useMeta()
  const [tab, setTab] = useState('review')
  const [items, setItems] = useState([])
  const [sel, setSel] = useState(null)
  const [err, setErr] = useState('')
  const [loading, setLoading] = useState(true)
  const [q, setQ] = useState('')
  const [graphOnly, setGraphOnly] = useState(false)
  const debounce = useRef(null)

  const load = useCallback((status) => {
    setLoading(true)
    getReview(status)
      .then((d) => { setItems(d); setErr('') })
      .catch(() => setErr('Could not reach the queue.'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { setSel(null); load(tab) }, [tab, load])

  // keep the active list fresh as matching verdicts stream in (debounced)
  useEffect(() => feed.onVerdict((v) => {
    if (v.status === tab) { clearTimeout(debounce.current); debounce.current = setTimeout(() => load(tab), 1000) }
  }), [tab, load])

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onBack() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onBack])

  useEffect(() => {
    if (sel && !items.some((i) => i.txn_id === sel.txn_id)) setSel(null)
  }, [items, sel])

  const needle = q.trim().toLowerCase()
  const filtered = items.filter((d) => {
    if (graphOnly && !hasGraph(d)) return false
    if (!needle) return true
    const t = d.txn || {}
    const reasons = [
      ...(d.reasons || []),
      ...((d.name_result && d.name_result.reasons) || []),
      ...((d.exposure_result && d.exposure_result.reasons) || []),
    ].join(' ')
    return `${t.bene_name || ''} ${t.wallet || ''} ${t.bene_country || ''} ${d.txn_id || ''} ${d.combined_verdict || ''} ${reasons}`
      .toLowerCase().includes(needle)
  })

  const resolve = (txnId) => {
    setItems((xs) => xs.filter((i) => i.txn_id !== txnId))
    setSel((s) => (s && s.txn_id === txnId ? null : s))
  }

  const VISIBLE = 120
  const visible = filtered.slice(0, VISIBLE)
  const meta = TABS[tab]
  return (
    <main className="review">
      <div className="review-bg"><Background intensity={0.5} ambient={0} onPick={setSel} /></div>
      <div className="review-scrim" />

      <header className="rev-head">
        <button className="back" onClick={onBack} title="Back to live view (Esc)">←</button>
        <div className="rev-head-title">
          <div className="rev-title"><span className="mark">◈</span> Review Desk</div>
          <div className="rev-sub">Click a metric to browse cleared · review · blocked</div>
        </div>
        <div className="rev-kpis">
          <Kpi n={counts.allowed} label="cleared" cls="ok" active={tab === 'allowed'} onClick={() => setTab('allowed')} />
          <Kpi n={counts.review} label="in review" cls="rev" active={tab === 'review'} onClick={() => setTab('review')} />
          <Kpi n={counts.blocked} label="blocked" cls="blk" active={tab === 'blocked'} onClick={() => setTab('blocked')} />
          <LiveBadge connected={connected} />
        </div>
      </header>

      <div className="rev-body">
        <aside className="queue">
          <div className="queue-top">
            <div className="queue-title">
              <span className={'qtitle-dot ' + meta.sev} />{meta.title}
              <span className="badge">{filtered.length}</span>
            </div>
            <div className="search">
              <SearchIcon />
              <input value={q} onChange={(e) => setQ(e.target.value)}
                     placeholder="Search name, country, reason…" />
              {q && <button className="search-clear" onClick={() => setQ('')} aria-label="Clear search">✕</button>}
            </div>
            <button className={'gfilter' + (graphOnly ? ' on' : '')} onClick={() => setGraphOnly((v) => !v)} type="button">
              <span className="gfilter-mark">⬡</span> Exposure graph only
            </button>
          </div>
          <div className="queue-list">
            {loading && <SkeletonRows />}
            {err && <div className="err pad">{err}</div>}
            {!loading && !err && filtered.length === 0 &&
              <div className="muted pad">{items.length ? 'No matches for this filter.' : meta.empty}</div>}
            {visible.map((d) => (
              <QueueItem key={d.txn_id} d={d} tab={tab} active={sel?.txn_id === d.txn_id} onClick={() => setSel(d)} />
            ))}
            {filtered.length > visible.length &&
              <div className="queue-more">+{filtered.length - visible.length} more — refine your search</div>}
          </div>
        </aside>

        <section className="detail">
          {sel ? <Dossier d={sel} onResolve={tab === 'review' ? resolve : undefined} /> : <EmptyDetail />}
        </section>
      </div>
    </main>
  )
}

function QueueItem({ d, tab, active, onClick }) {
  const t = d.txn || {}
  const crypto = !!t.wallet && !t.bene_name
  const name = t.bene_name || (t.wallet ? shortWallet(t.wallet) : d.txn_id)
  const cc = (t.bene_country || '').toUpperCase()
  const st = d.status || tab || 'review'
  const sev = st === 'allowed' ? 'ok' : st === 'blocked' ? 'blk' : 'rev'
  const label = st === 'allowed' ? 'CLEARED' : st === 'blocked' ? 'BLOCKED' : 'REVIEW'
  return (
    <button className={'qitem' + (active ? ' active' : '')} onClick={onClick}>
      <span className="avatar" style={{ '--h': hue(name) }}>{crypto ? '◈' : initials(name)}</span>
      <span className="qtext">
        <span className="qname">{name}{hasGraph(d) && <span className="qgraph" title="has exposure graph">⬡</span>}</span>
        <span className="qmeta">{[flag(cc), cc, t.channel || 'fiat'].filter(Boolean).join(' · ')}</span>
      </span>
      <span className="qside">
        {t.amount != null && <span className="qamt">{fmtAmount(t.amount, t.currency)}</span>}
        <span className={'qsev ' + sev}>{label}</span>
      </span>
    </button>
  )
}

function EmptyDetail() {
  return (
    <div className="empty">
      <div className="empty-mark">◈</div>
      <h3>Select a flagged payment</h3>
      <p>Pick an item from the queue — or click a dot in the background — to see the full
        dossier: both screening modules, the original payment, and why it was flagged.</p>
    </div>
  )
}

function Dossier({ d, onResolve, hideHead }) {
  const t = d.txn || {}
  const crypto = !!t.wallet && !t.bene_name
  const name = t.bene_name || t.wallet || d.txn_id
  const confidence = Math.max(Number(d.name_result?.score) || 0, Number(d.exposure_result?.score) || 0)
  return (
    <div className="dossier">
      {hideHead ? (
        <h2 className="modal-name">{name}</h2>
      ) : (
        <div className="dossier-hero">
          <span className="hero-avatar" style={{ '--h': hue(name) }}>{crypto ? '◈' : initials(name)}</span>
          <div className="hero-main">
            <h2 className="hero-name">{name}</h2>
            <div className="hero-tags">
              <span className={'pill ' + statusClass(d.combined_verdict)}>{d.combined_verdict}</span>
              <span className="tag">{t.channel || 'fiat'}</span>
              <span className="tag mono">{d.txn_id}</span>
              {d.decided_at && <span className="tag">{fmtTime(d.decided_at)}</span>}
            </div>
          </div>
        </div>
      )}

      <div className="route">
        <div className="route-end">
          <div className="route-flag">{flag(t.orig_country) || '🏳️'}</div>
          <div className="route-lbl">Sender</div>
          <div className="route-cc">{(t.orig_country || '—').toUpperCase()}</div>
        </div>
        <div className="route-line">
          <span className="route-amt">{t.amount != null ? fmtAmount(t.amount, t.currency) : 'payment'}</span>
          <span className="route-rail">{t.rail || t.channel || '—'}</span>
        </div>
        <div className="route-end">
          <div className="route-flag">{flag(t.bene_country) || '🏳️'}</div>
          <div className="route-lbl">Recipient</div>
          <div className="route-cc">{(t.bene_country || '—').toUpperCase()}</div>
        </div>
      </div>

      <RiskMeter score={confidence} />

      <div className="card">
        <div className="card-h">Payment details</div>
        <div className="grid">
          <Field k="Amount" v={t.amount != null ? fmtAmount(t.amount, t.currency) : '—'} />
          <Field k="Rail" v={t.rail} />
          <Field k="Sender country" v={t.orig_country} />
          <Field k="Recipient country" v={t.bene_country} />
          <Field k="DOB" v={t.bene_dob} />
          <Field k="Passport" v={t.bene_passport} />
          <Field k="National ID" v={t.bene_national_id} />
          <Field k="Wallet" v={t.wallet} />
        </div>
      </div>

      <ModuleCard title="Identity screening" icon="🪪" r={d.name_result} />
      <ModuleCard title="Crypto graph exposure" icon="🕸️" r={d.exposure_result} />

      {d.reasons?.length > 0 && (
        <div className="card">
          <div className="card-h">Why it was flagged</div>
          <ul className="reasons">{d.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>
        </div>
      )}

      {onResolve && (
        <div className="actions">
          <button className="act clear" onClick={() => onResolve(d.txn_id)}>✓ Clear</button>
          <button className="act escalate" onClick={() => onResolve(d.txn_id)}>⚑ Escalate</button>
          <button className="act block" onClick={() => onResolve(d.txn_id)}>⦸ Block</button>
        </div>
      )}
    </div>
  )
}

function RiskMeter({ score }) {
  const pct = Math.round(Math.max(0, Math.min(1, Number(score) || 0)) * 100)
  const band = pct >= 80 ? 'High' : pct >= 40 ? 'Elevated' : 'Low'
  return (
    <div className="meter" style={{ '--p': pct }}>
      <div className="meter-top">
        <span>Match confidence</span>
        <span className="meter-val">{pct}% · {band}</span>
      </div>
      <div className="meter-track"><div className="meter-knob" /></div>
    </div>
  )
}

function ModuleCard({ title, icon, r }) {
  if (!r || !r.applicable) {
    return <div className="card na"><span className="card-h">{icon} {title}</span><span className="na-tag">not applicable</span></div>
  }
  // for exposure, the decision is driven by risk_score; raw graph exposure_score is lower
  const strength = r.detail?.risk_score != null ? Number(r.detail.risk_score) : Number(r.score)
  const pct = Math.round(Math.max(0, Math.min(1, strength || 0)) * 100)
  return (
    <div className="card">
      <div className="card-h between">
        <span>{icon} {title}</span>
        <span className={'pill sm ' + verdictClass(r.verdict)}>{r.verdict}</span>
      </div>
      <div className="mod-row">
        <div className={'ring ' + verdictClass(r.verdict)} style={{ '--p': pct }}>
          <span>{pct}<small>%</small></span>
        </div>
        <div className="mod-info">
          <Field k="Matched entity" v={r.matched_name} />
          <Field k="Entity ID" v={r.entity_id} />
        </div>
      </div>
      {r.reasons?.length > 0 && <ul className="reasons sm">{r.reasons.map((x, i) => <li key={i}>{x}</li>)}</ul>}
      {r.detail?.graph?.nodes?.length > 0 && <ExposureGraph graph={r.detail.graph} />}
      {r.detail?.chain?.length > 1 && <ExposureChain steps={r.detail.chain} />}
      {r.detail?.evidence?.length > 0 && <ExposureEvidence items={r.detail.evidence} />}
    </div>
  )
}

function ExposureChain({ steps }) {
  if (!steps?.length) return null
  return (
    <div className="xchain">
      <div className="xsec-h">Full route — how the chain was traced</div>
      <ol className="xchain-list">
        {steps.map((s) => (
          <li key={s.step} className={'xchain-step ' + riskCls(s.risk)}>
            <span className="xchain-bullet" />
            <span className="xchain-body">
              <span className="xchain-node">
                {clip(s.label, 30)}
                <span className="xchain-tags">
                  {[s.type, s.risk !== 'NONE' ? s.risk : null, s.country ? s.country.toUpperCase() : null]
                    .filter(Boolean).join(' · ')}
                </span>
              </span>
              <span className="xchain-via">{s.via}{s.amount ? ` · ${fmtAmount(s.amount)}` : ''}</span>
            </span>
          </li>
        ))}
      </ol>
    </div>
  )
}

function ExposureEvidence({ items }) {
  if (!items?.length) return null
  return (
    <div className="xev-list">
      <div className="xsec-h">Why it scored — evidence</div>
      {items.map((e, i) => (
        <div className="xev" key={i}>
          <div className="xev-top">
            <span className="xev-code">{String(e.reason_code || '').replace(/_/g, ' ')}</span>
            {e.severity && <span className={'xev-sev ' + sevCls(e.severity)}>{e.severity}</span>}
            {e.score_contribution != null && <span className="xev-score">{fmtContrib(e.score_contribution)}</span>}
          </div>
          {e.explanation && <div className="xev-exp">{e.explanation}</div>}
        </div>
      ))}
    </div>
  )
}

function ExposureGraph({ graph }) {
  const nodes = graph?.nodes || []
  const edges = graph?.edges || []
  if (!nodes.length) return null
  const R = 17, GAP = 150, PADX = 50, CY = 56, H = 132
  const W = PADX * 2 + Math.max(1, nodes.length - 1) * GAP
  const xs = nodes.map((_, i) => PADX + i * GAP)
  return (
    <div className="xgraph">
      <div className="xgraph-scroll">
        {/* responsive: scales to the panel width so the final (red) source node is always
            in view, no horizontal scrolling needed */}
        <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} preserveAspectRatio="xMidYMid meet"
             className="xgraph-svg">
          <defs>
            <marker id="xg-arrow" markerWidth="9" markerHeight="9" refX="6.5" refY="3" orient="auto">
              <path d="M0,0 L6.5,3 L0,6 Z" fill="rgba(255,255,255,0.55)" />
            </marker>
          </defs>
          {edges.map((e, i) => {
            const x1 = xs[i], x2 = xs[i + 1], y = CY, mx = (x1 + x2) / 2
            const inbound = String(e.flow || '').includes('inbound')
            return (
              <g key={i}>
                <line x1={x1 + R} y1={y} x2={x2 - R} y2={y} stroke="rgba(255,255,255,0.16)" strokeWidth="1.5" />
                <line x1={inbound ? x2 - R : x1 + R} y1={y} x2={inbound ? x1 + R : x2 - R} y2={y}
                      stroke="transparent" markerEnd="url(#xg-arrow)" />
                <text x={mx} y={y - 11} className="xg-edge">{(e.type || '').replace(/_/g, ' ')}</text>
                {e.amount ? <text x={mx} y={y + 17} className="xg-amt">{fmtAmount(e.amount)}</text> : null}
              </g>
            )
          })}
          {nodes.map((n, i) => (
            <g key={n.id + i} transform={`translate(${xs[i]},${CY})`}>
              <circle r={R} className={'xg-node ' + riskCls(n.risk)
                + (n.role === 'account' ? ' acct' : '') + (n.role === 'source' ? ' src' : '')} />
              <text className="xg-glyph" y="4.5">{glyph(n.type)}</text>
              <text className="xg-label" y={R + 16}>{clip(n.label, 16)}</text>
              <text className="xg-sub" y={R + 29}>
                {n.role === 'source' ? 'RISK SOURCE' : n.role === 'account' ? 'PAYEE' : (n.type || '')}
              </text>
            </g>
          ))}
        </svg>
      </div>
      <div className="xgraph-legend">
        <span><i className="xg-dot sanc" /> sanctioned</span>
        <span><i className="xg-dot susp" /> suspicious</span>
        <span><i className="xg-dot none" /> clean</span>
        <span className="xg-meta">{graph.depth} hop{graph.depth === 1 ? '' : 's'} to source · exposure {Math.round((graph.score || 0) * 100)}%</span>
      </div>
    </div>
  )
}

function Field({ k, v }) {
  return <div className="field"><span className="fk">{k}</span><span className="fv">{v || '—'}</span></div>
}

function TxnModal({ d, onClose }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])
  return (
    <div className="modal-backdrop" onClick={(e) => { e.stopPropagation(); onClose() }}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-top">
          <span className={'pill ' + statusClass(d.combined_verdict)}>{d.combined_verdict}</span>
          <span className="modal-id">{d.txn_id}</span>
          <button className="modal-close" onClick={onClose} aria-label="Close">✕</button>
        </div>
        <div className="modal-body"><Dossier d={d} hideHead /></div>
      </div>
    </div>
  )
}

function SkeletonRows() {
  return <>{Array.from({ length: 7 }).map((_, i) => <div key={i} className="skel" />)}</>
}

function SearchIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="2" strokeLinecap="round">
      <circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" />
    </svg>
  )
}

/* ----------------------------- helpers ----------------------------- */
function statusClass(verdict) { return verdict === 'MATCH' ? 'blk' : verdict === 'REVIEW' ? 'rev' : 'ok' }
function verdictClass(verdict) { return verdict === 'MATCH' ? 'blk' : verdict === 'REVIEW' ? 'rev' : 'ok' }

function fmtAmount(amount, currency) {
  const n = Number(amount)
  const s = Number.isFinite(n) ? n.toLocaleString(undefined, { maximumFractionDigits: 2 }) : amount
  return currency ? `${s} ${currency}` : `${s}`
}

function fmtTime(iso) {
  try { return new Date(iso).toLocaleTimeString() } catch { return iso }
}

function initials(name) {
  const parts = (name || '').trim().split(/\s+/).filter(Boolean)
  if (!parts.length) return '#'
  return (parts[0][0] + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase()
}

function shortWallet(w) {
  return w && w.length > 14 ? `${w.slice(0, 8)}…${w.slice(-4)}` : w
}

function hue(s) {
  let h = 0
  for (const ch of (s || '')) h = (h * 31 + ch.charCodeAt(0)) % 360
  return h
}

function flag(cc) {
  const c = (cc || '').toUpperCase()
  if (!/^[A-Z]{2}$/.test(c)) return ''
  return String.fromCodePoint(...[...c].map((ch) => 0x1f1e6 + ch.charCodeAt(0) - 65))
}

function riskCls(r) {
  const x = (r || '').toUpperCase()
  return x === 'SANCTIONED' ? 'sanc' : x === 'SUSPICIOUS' ? 'susp' : 'none'
}
function glyph(type) {
  const t = (type || '').toUpperCase()
  return { IBAN: '€', ACCOUNT: '€', PERSON: 'P', COMPANY: 'Co', BANK: 'B', WALLET: '◈' }[t] || '•'
}
function clip(s, n) {
  s = String(s || '')
  return s.length > n ? s.slice(0, n - 1) + '…' : s
}
function sevCls(sev) {
  const x = (sev || '').toUpperCase()
  return x === 'CRITICAL' || x === 'HIGH' ? 'blk' : x === 'MEDIUM' ? 'rev' : 'ok'
}
function fmtContrib(v) {
  const n = Number(v)
  if (!Number.isFinite(n)) return ''
  return (n >= 0 ? '+' : '') + n.toFixed(2)
}
