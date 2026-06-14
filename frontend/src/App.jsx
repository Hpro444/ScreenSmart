import React, { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Background from './Background.jsx'
import { feed } from './feed.js'
import { getReview, decide, getNode, streamChat } from './api.js'

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
    // back (→ landing) swaps instantly with no animation; only forward (→ review) animates
    if (REDUCE || target !== 'review') { setView(target); return }
    busy.current = true
    setDir('fwd')
    setAnim(true)                                          // one compositor keyframe sweeps in→hold→out
    setTimeout(() => { setView(target); setEntering(true) }, 300)  // swap while fully covered
    setTimeout(() => { setAnim(false); setEntering(false); busy.current = false }, 700)
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

  const load = useCallback((status) => {
    setLoading(true)
    // fetch the whole current list on open (cleared can be huge, so cap it) — keeps the
    // count stable across visits instead of resetting to a small page
    const limit = status === 'allowed' ? 1500 : 6000
    getReview(status, limit)
      .then((d) => { setItems(d); setErr('') })
      .catch(() => setErr('Could not reach the queue.'))
      .finally(() => setLoading(false))
  }, [])

  // full fetch only on tab switch / first load
  useEffect(() => { setSel(null); setItems([]); load(tab) }, [tab, load])  // clear so no stale rows show under the skeletons

  // live updates: merge each new verdict in place instead of refetching — existing rows
  // never move (no reordering / no flicker); brand-new ones are appended to the end so the
  // list grows quietly without jumping.
  useEffect(() => feed.onVerdict((v) => {
    if (v.status !== tab) return
    setItems((xs) => {
      const i = xs.findIndex((d) => d.txn_id === v.txn_id)
      if (i !== -1) { const c = xs.slice(); c[i] = v; return c }   // update in place
      const next = xs.concat(v)                                    // append new arrival
      return next.length > 7000 ? next.slice(next.length - 7000) : next
    })
  }), [tab])

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onBack() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onBack])

  useEffect(() => {
    if (sel && !items.some((i) => i.txn_id === sel.txn_id)) setSel(null)
  }, [items, sel])

  const needle = q.trim().toLowerCase()
  // memoised so the filter (over thousands of rows) only re-runs on real input changes —
  // NOT on every live verdict tick (which would jank scrolling)
  const filtered = useMemo(() => items.filter((d) => {
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
  }), [items, needle, graphOnly])

  // record the analyst decision (persists + flags the payee account for block/escalate),
  // then optimistically drop it from the queue
  const resolve = useCallback((txnId, decision) => {
    decide(txnId, decision).catch(() => {})
    setItems((xs) => xs.filter((i) => i.txn_id !== txnId))
    setSel((s) => (s && s.txn_id === txnId ? null : s))
  }, [])
  const onSelect = useCallback((d) => setSel(d), [])

  const VISIBLE = 120
  const visible = useMemo(() => filtered.slice(0, VISIBLE), [filtered])
  const meta = TABS[tab]
  // the badge should reflect the TRUE total for this status (from the live counts), not the
  // loaded slice — cleared can be 40k+ while we only fetch the latest ~1.5k for the list.
  const filtering = !!needle || graphOnly
  const total = counts[tab] ?? items.length
  const badgeN = filtering ? filtered.length : total
  const partial = !filtering && items.length < total
  return (
    <main className="review">
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
              <span className="badge">{Number(badgeN).toLocaleString()}</span>
            </div>
            {partial && <div className="queue-hint">showing latest {items.length.toLocaleString()}</div>}
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
            {loading ? <SkeletonRows /> : err ? <div className="err pad">{err}</div>
              : filtered.length === 0
                ? <div className="muted pad">{items.length ? 'No matches for this filter.' : meta.empty}</div>
                : <>
                    {visible.map((d) => (
                      <QueueItem key={d.txn_id} d={d} tab={tab} active={sel?.txn_id === d.txn_id} onSelect={onSelect} />
                    ))}
                    {filtered.length > visible.length &&
                      <div className="queue-more">+{filtered.length - visible.length} more — refine your search</div>}
                  </>}
          </div>
        </aside>

        <section className="detail">
          {sel ? <Dossier d={sel} onResolve={tab === 'review' ? resolve : undefined} /> : <EmptyDetail />}
        </section>
      </div>
    </main>
  )
}

const QueueItem = memo(function QueueItem({ d, tab, active, onSelect }) {
  const t = d.txn || {}
  const crypto = !!t.wallet && !t.bene_name
  const name = t.bene_name || (t.wallet ? shortWallet(t.wallet) : d.txn_id)
  const cc = (t.bene_country || '').toUpperCase()
  const st = d.status || tab || 'review'
  const sev = st === 'allowed' ? 'ok' : st === 'blocked' ? 'blk' : 'rev'
  const label = st === 'allowed' ? 'CLEARED' : st === 'blocked' ? 'BLOCKED' : 'REVIEW'
  return (
    <button className={'qitem' + (active ? ' active' : '')} onClick={() => onSelect(d)}>
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
})

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

const Dossier = memo(function Dossier({ d, onResolve, hideHead }) {
  const t = d.txn || {}
  const crypto = !!t.wallet && !t.bene_name
  const name = t.bene_name || t.wallet || d.txn_id
  const confidence = Math.max(Number(d.name_result?.score) || 0, Number(d.exposure_result?.score) || 0)
  const [nodeKey, setNodeKey] = useState(null)   // drill-into-graph-node explorer
  const [chatOpen, setChatOpen] = useState(false)
  // chat session lives here (not in the drawer) so the stream keeps running — and finishes
  // into the persisted session — even if the user closes the chat. It only resets/aborts
  // when the reviewed profile changes.
  const [chat, setChat] = useState({ messages: [], busy: false })
  const chatRef = useRef(chat); useEffect(() => { chatRef.current = chat }, [chat])
  const chatAbort = useRef(null)
  const startedFor = useRef(null)

  const sendChat = useCallback((text) => {
    const history = text ? [...chatRef.current.messages, { role: 'user', content: text }] : []
    setChat({ messages: [...history, { role: 'assistant', content: '' }], busy: true })
    if (chatAbort.current) chatAbort.current.abort()
    chatAbort.current = new AbortController()
    streamChat(d, history, (tok) => setChat((c) => {
      const m = c.messages.slice()
      m[m.length - 1] = { role: 'assistant', content: m[m.length - 1].content + tok }
      return { ...c, messages: m }
    }), chatAbort.current.signal)
      .catch((e) => {
        if (e && e.name === 'AbortError') return
        setChat((c) => {
          const m = c.messages.slice()
          if (m.length) m[m.length - 1] = { role: 'assistant', content: '⚠️ Assistant unavailable — is the chatbot / Ollama service reachable?' }
          return { ...c, messages: m }
        })
      })
      .finally(() => setChat((c) => ({ ...c, busy: false })))
  }, [d])

  // profile changed → abort any in-flight stream and clear the session
  useEffect(() => {
    if (chatAbort.current) chatAbort.current.abort()
    setChat({ messages: [], busy: false })
    startedFor.current = null
  }, [d.txn_id])

  // fetch the initial explanation once per profile, the first time the chat is opened
  useEffect(() => {
    if (chatOpen && startedFor.current !== d.txn_id) {
      startedFor.current = d.txn_id
      sendChat(null)
    }
  }, [chatOpen, d.txn_id, sendChat])

  return (
    <div className="dossier">
      {nodeKey && <NodeExplorer startKey={nodeKey} onClose={() => setNodeKey(null)} />}
      {chatOpen && <ChatPanel dossier={d} chat={chat} onSend={sendChat} onClose={() => setChatOpen(false)} />}
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
          <button className="explain-btn" onClick={() => setChatOpen(true)} title="Ask the assistant">
            💬 Explain
          </button>
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
      <ModuleCard title="Network exposure" icon="🕸️" r={d.exposure_result} onNodeClick={setNodeKey} />

      {d.reasons?.length > 0 && (
        <div className="card">
          <div className="card-h">Why it was flagged</div>
          <ul className="reasons">{d.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>
        </div>
      )}

      {onResolve && (
        <>
          <div className="actions">
            <button className="act clear" onClick={() => onResolve(d.txn_id, 'clear')}>✓ Clear</button>
            <button className="act escalate" onClick={() => onResolve(d.txn_id, 'escalate')}>⚑ Escalate</button>
            <button className="act block" onClick={() => onResolve(d.txn_id, 'block')}>⦸ Block</button>
          </div>
          {(d.txn?.bene_account) &&
            <div className="act-note">Escalate / Block flags account <code>{clip(d.txn.bene_account, 22)}</code> as a risk node for future exposure tracing.</div>}
        </>
      )}
    </div>
  )
})

function NodeExplorer({ startKey, onClose }) {
  const [stack, setStack] = useState([startKey])   // navigation history of node keys
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')
  const current = stack[stack.length - 1]

  useEffect(() => {
    let alive = true
    setLoading(true); setErr('')
    getNode(current)
      .then((d) => { if (alive) { if (d) setData(d); else setErr('This node isn’t in the graph.') } })
      .catch(() => alive && setErr('Could not load node.'))
      .finally(() => alive && setLoading(false))
    return () => { alive = false }
  }, [current])

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const push = (k) => { if (k && k !== current) setStack((s) => [...s, k]) }
  const back = () => setStack((s) => (s.length > 1 ? s.slice(0, -1) : s))

  const node = data?.node
  const exp = data?.exposure
  return (
    <div className="modal-backdrop" onClick={(e) => { e.stopPropagation(); onClose() }}>
      <div className="modal node-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-top">
          {stack.length > 1
            ? <button className="modal-close" onClick={back} title="Back">←</button>
            : <span className="node-kicker">NODE</span>}
          <span className="modal-id">{clip(current, 34)}</span>
          <button className="modal-close" onClick={onClose} aria-label="Close">✕</button>
        </div>
        <div className="modal-body">
          {loading && <div className="muted pad">Loading node…</div>}
          {err && !loading && <div className="muted pad">{err}</div>}
          {!loading && !err && node && (
            <div className="dossier">
              <div className="dossier-hero">
                <span className="hero-avatar" style={{ '--h': hue(node.display_name || node.node_key) }}>
                  {glyph(node.node_type)}
                </span>
                <div className="hero-main">
                  <h2 className="hero-name">{node.display_name || node.node_key}</h2>
                  <div className="hero-tags">
                    {node.risk_level && node.risk_level !== 'NONE' &&
                      <span className={'pill ' + riskPill(node.risk_level)}>{node.risk_level}</span>}
                    <span className="tag">{node.node_type}</span>
                    {node.country && <span className="tag">{flag(node.country)} {node.country.toUpperCase()}</span>}
                    <span className="tag">{data.degree} link{data.degree === 1 ? '' : 's'}</span>
                    {node.risk_source && <span className="tag">{node.risk_source}</span>}
                  </div>
                </div>
              </div>

              <div className="grid">
                <Field k="Node key" v={node.node_key} />
                <Field k="Type" v={node.node_type} />
                {node.created_at && <Field k="In graph since" v={fmtDate(node.created_at)} />}
                {data.activity?.first_seen && <Field k="Active period"
                  v={`${fmtDate(data.activity.first_seen)} → ${fmtDate(data.activity.last_seen)}`} />}
              </div>

              {data.belongs_to?.length > 0 && (
                <div className="card">
                  <div className="card-h">Belongs to / held by</div>
                  <NodeChips items={data.belongs_to} onPick={push} />
                </div>
              )}
              {data.controls?.length > 0 && (
                <div className="card">
                  <div className="card-h">Controls ({data.controls.length})</div>
                  <NodeChips items={data.controls} onPick={push} />
                </div>
              )}

              {(data.activity?.sent_tx > 0 || data.activity?.received_tx > 0) && (
                <div className="card">
                  <div className="card-h">Activity</div>
                  <div className="grid">
                    <Field k="Total sent" v={fmtAmount(data.activity.total_sent)} />
                    <Field k="Total received" v={fmtAmount(data.activity.total_received)} />
                    <Field k="Sent — txns / payees" v={`${data.activity.sent_tx} / ${data.activity.counterparties_out}`} />
                    <Field k="Received — txns / payers" v={`${data.activity.received_tx} / ${data.activity.counterparties_in}`} />
                  </div>
                </div>
              )}

              {data.counterparties?.sent_to?.length > 0 && (
                <div className="card">
                  <div className="card-h">Top recipients (sent to)</div>
                  <CounterpartyList items={data.counterparties.sent_to} onPick={push} />
                </div>
              )}
              {data.counterparties?.received_from?.length > 0 && (
                <div className="card">
                  <div className="card-h">Top sources (received from)</div>
                  <CounterpartyList items={data.counterparties.received_from} onPick={push} />
                </div>
              )}
              {data.shared_identifiers?.length > 0 && (
                <div className="card">
                  <div className="card-h">Shares identifiers with</div>
                  <NodeChips items={data.shared_identifiers} onPick={push} />
                </div>
              )}

              {exp ? (
                <>
                  <div className="card-h" style={{ marginTop: 4 }}>Exposure</div>
                  <RiskMeter score={exp.score} />
                  {exp.reason && <div className="card"><div className="card-h">Assessment</div>
                    <div className="xev-exp">{exp.reason}</div></div>}
                  {data.graph?.nodes?.length > 0 && (
                    <div className="card">
                      <div className="card-h">Exposure path from this node</div>
                      <ExposureGraph graph={data.graph} onNodeClick={push} />
                    </div>
                  )}
                  {data.chain?.length > 1 && <ExposureChain steps={data.chain} />}
                </>
              ) : (
                <div className="card"><div className="card-h">Exposure</div>
                  <div className="xev-exp">No exposure path recorded — this node isn’t linked
                    to a sanctioned or suspicious source in the graph.</div></div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// Presentational drawer. The conversation + streaming live in the parent (Dossier) so the
// reply keeps streaming even after this drawer is closed.
function ChatPanel({ dossier, chat, onSend, onClose }) {
  const [input, setInput] = useState('')
  const bodyRef = useRef(null)
  const busy = chat.busy

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  useEffect(() => { if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight }, [chat.messages])

  const submit = (e) => {
    e.preventDefault()
    const text = input.trim()
    if (!text || busy) return
    setInput('')
    onSend(text)
  }
  const who = dossier.txn?.bene_name || dossier.txn?.wallet || dossier.txn_id
  return (
    <div className="chat-drawer">
      <div className="chat-head">
        <span className="chat-title">💬 Why was this flagged?</span>
        <span className="chat-sub">{clip(who, 26)}</span>
        <button className="modal-close" onClick={onClose} aria-label="Close">✕</button>
      </div>
      <div className="chat-body" ref={bodyRef}>
        {chat.messages.map((m, i) => (
          <div key={i} className={'chat-msg ' + m.role}>
            {m.role === 'assistant' && <span className="chat-ava">◈</span>}
            <div className="chat-bubble">
              {m.content
                ? m.content.split('\n').map((ln, j) => <p key={j}>{renderBold(ln)}</p>)
                : <span className="chat-typing"><i /><i /><i /></span>}
            </div>
          </div>
        ))}
      </div>
      <form className="chat-input" onSubmit={submit}>
        <input value={input} onChange={(e) => setInput(e.target.value)}
               placeholder="Ask a follow-up…" disabled={busy && chat.messages.length <= 1} />
        <button type="submit" disabled={busy || !input.trim()}>↑</button>
      </form>
    </div>
  )
}

function renderBold(line) {
  // tiny **bold** renderer
  const parts = line.split(/(\*\*[^*]+\*\*)/g)
  return parts.map((p, i) => p.startsWith('**') && p.endsWith('**')
    ? <strong key={i}>{p.slice(2, -2)}</strong> : <span key={i}>{p}</span>)
}

function NodeChips({ items, onPick }) {
  return (
    <div className="node-chips">
      {items.map((n, i) => (
        <button key={n.id + i} className={'node-chip ' + riskCls(n.risk)} onClick={() => onPick(n.id)} title={n.id}>
          <span className="nc-glyph">{glyph(n.type)}</span>
          <span className="nc-label">{clip(n.label, 22)}</span>
          {n.relation && <span className="nc-rel">{n.relation.replace(/_/g, ' ').toLowerCase()}</span>}
          {n.risk && n.risk !== 'NONE' && <span className={'nc-dot ' + riskCls(n.risk)} />}
        </button>
      ))}
    </div>
  )
}

function CounterpartyList({ items, onPick }) {
  return (
    <div className="cp-list">
      {items.map((n, i) => (
        <button key={n.id + i} className="cp-row" onClick={() => onPick(n.id)} title={n.id}>
          <span className={'cp-glyph ' + riskCls(n.risk)}>{glyph(n.type)}</span>
          <span className="cp-main">
            <span className="cp-name">{clip(n.label, 26)}{n.risk && n.risk !== 'NONE' &&
              <span className={'nc-dot ' + riskCls(n.risk)} />}</span>
            <span className="cp-meta">{[flag(n.country), n.country ? n.country.toUpperCase() : null, `${n.transaction_count} txn`]
              .filter(Boolean).join(' · ')}</span>
          </span>
          <span className="cp-amt">{fmtAmount(n.amount)}</span>
        </button>
      ))}
    </div>
  )
}

// SVG donut — composites cleanly (no conic-gradient repaint lag while the panel scrolls)
function Ring({ pct, cls }) {
  const R = 24, C = 2 * Math.PI * R
  const off = C * (1 - Math.max(0, Math.min(100, pct)) / 100)
  const col = cls === 'blk' ? '#f74856' : cls === 'rev' ? '#f5c32d' : '#28e68c'
  return (
    <svg width="62" height="62" viewBox="0 0 62 62" className="ringsvg">
      <circle cx="31" cy="31" r={R} fill="none" stroke="rgba(255,255,255,0.09)" strokeWidth="6" />
      <circle cx="31" cy="31" r={R} fill="none" stroke={col} strokeWidth="6" strokeLinecap="round"
              strokeDasharray={C} strokeDashoffset={off} transform="rotate(-90 31 31)" />
      <text x="31" y="35" textAnchor="middle" className="ringsvg-t">
        {pct}<tspan className="ringsvg-s">%</tspan>
      </text>
    </svg>
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

function ModuleCard({ title, icon, r, onNodeClick }) {
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
        <Ring pct={pct} cls={verdictClass(r.verdict)} />
        <div className="mod-info">
          <Field k="Matched entity" v={r.matched_name} />
          <Field k="Entity ID" v={r.entity_id} />
        </div>
      </div>
      {r.reasons?.length > 0 && <ul className="reasons sm">{r.reasons.map((x, i) => <li key={i}>{x}</li>)}</ul>}
      {r.detail?.graph?.nodes?.length > 0 && <ExposureGraph graph={r.detail.graph} onNodeClick={onNodeClick} />}
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

function ExposureGraph({ graph, onNodeClick }) {
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
            <g key={n.id + i} transform={`translate(${xs[i]},${CY})`}
               className={onNodeClick ? 'xg-clickable' : ''}
               onClick={onNodeClick ? (e) => { e.stopPropagation(); onNodeClick(n.id) } : undefined}>
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
      {onNodeClick && <div className="xgraph-tip">Click any node to inspect it</div>}
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
  // enough rows to fill the panel so the whole list reads as loading (no half-skeleton/
  // half-content); excess is clipped by the list's overflow
  return <>{Array.from({ length: 16 }).map((_, i) => <div key={i} className="skel" />)}</>
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
function fmtDate(iso) {
  try { return new Date(iso).toLocaleDateString() } catch { return iso }
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
function riskPill(r) {
  const x = (r || '').toUpperCase()
  return x === 'SANCTIONED' ? 'blk' : x === 'SUSPICIOUS' ? 'rev' : 'ok'
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
