import React, { useEffect, useRef } from 'react'
import { feed } from './feed.js'

// Each screened payment is a glowing particle that streams in from the left. At a
// "decision line" near the middle it resolves:
//   allowed (green)  → keeps flowing right and exits
//   review  (amber)  → lifts upward and fades
//   blocked (red)    → falls downward and fades
// Every dot is a real verdict from the live feed, spawned the instant it's processed.
// Hovering a dot freezes it and shows the name; clicking it opens the full transaction.

const COLORS = {
  allowed: [40, 230, 140],
  review: [245, 195, 45],
  blocked: [244, 72, 86],
}
const BG = [7, 10, 18]
const HOVER_R = 22   // px — how close the cursor must be to grab a dot
const CLICK_R = 26

// ambient distribution (opt-in fallback only; off by default)
const AMBIENT = [...Array(88).fill('allowed'), ...Array(9).fill('review'), ...Array(3).fill('blocked')]

function makeSprite([r, g, b]) {
  const s = 64
  const c = document.createElement('canvas')
  c.width = c.height = s
  const ctx = c.getContext('2d')
  const grd = ctx.createRadialGradient(s / 2, s / 2, 0, s / 2, s / 2, s / 2)
  grd.addColorStop(0, `rgba(${r},${g},${b},1)`)
  grd.addColorStop(0.22, `rgba(${r},${g},${b},0.6)`)
  grd.addColorStop(1, `rgba(${r},${g},${b},0)`)
  ctx.fillStyle = grd
  ctx.fillRect(0, 0, s, s)
  return c
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath()
  ctx.moveTo(x + r, y)
  ctx.arcTo(x + w, y, x + w, y + h, r)
  ctx.arcTo(x + w, y + h, x, y + h, r)
  ctx.arcTo(x, y + h, x, y, r)
  ctx.arcTo(x, y, x + w, y, r)
  ctx.closePath()
}

export default function Background({ intensity = 1, ambient = 0, onPick }) {
  const ref = useRef(null)
  const onPickRef = useRef(onPick)
  useEffect(() => { onPickRef.current = onPick })

  useEffect(() => {
    const canvas = ref.current
    const ctx = canvas.getContext('2d', { alpha: false })
    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    const sprites = {
      allowed: makeSprite(COLORS.allowed),
      review: makeSprite(COLORS.review),
      blocked: makeSprite(COLORS.blocked),
    }
    const particles = []
    const MAX = 1600
    let W = 0, H = 0
    let mouseX = -1, mouseY = -1, hover = null

    function resize() {
      const w = canvas.clientWidth
      const h = canvas.clientHeight
      if (!w || !h) return                          // ignore transient zero/partial layout
      if (w === W && h === H) return                // no real change → don't wipe the field
      W = w; H = h
      canvas.width = Math.floor(W * dpr)
      canvas.height = Math.floor(H * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.fillStyle = `rgb(${BG[0]},${BG[1]},${BG[2]})`
      ctx.fillRect(0, 0, W, H)
    }
    // ResizeObserver re-measures whenever the canvas box actually settles — so a measurement
    // taken mid-transition (which sized the backing store wrong → blurry/oversized dots) is
    // corrected the moment layout is final.
    const ro = new ResizeObserver(() => resize())
    ro.observe(canvas)
    resize()
    requestAnimationFrame(resize)                   // re-measure after the transition's first frame
    window.addEventListener('resize', resize)

    function spawn(input) {
      if (particles.length >= MAX) return
      const isObj = input && typeof input === 'object'
      const status = (isObj ? input.status : input) || 'allowed'
      const v = isObj ? input : null
      const name = v ? (v.txn?.bene_name || v.txn?.wallet || v.txn_id) : null
      const speed = (W / 760) * (0.55 + Math.random() * 0.95) * intensity
      particles.push({
        status, v, name,
        x: -20,
        y: Math.random() * H,
        vx: speed,
        vy: (Math.random() - 0.5) * 0.2,
        size: 2.0 + Math.random() * 2.2,
        decided: false,
        decisionX: W * (0.4 + Math.random() * 0.24),
        alpha: 0,
        life: 1,
      })
    }

    // one dot per processed transaction, the instant its verdict arrives
    const off = feed.onVerdict((v) => spawn(v))

    function nearest(px, py, radius) {
      let best = null, bestD = radius * radius
      for (const p of particles) {
        if (!p.v) continue                 // only real, clickable dots
        const dx = p.x - px, dy = p.y - py, d = dx * dx + dy * dy
        if (d < bestD) { bestD = d; best = p }
      }
      return best
    }

    function onMove(e) { const r = canvas.getBoundingClientRect(); mouseX = e.clientX - r.left; mouseY = e.clientY - r.top }
    function onLeave() { mouseX = mouseY = -1; hover = null; canvas.style.cursor = 'default' }
    function onClick(e) {
      const r = canvas.getBoundingClientRect()
      const hit = nearest(e.clientX - r.left, e.clientY - r.top, CLICK_R)
      if (hit && onPickRef.current) {
        e.stopPropagation()              // don't let the landing's "click → enter" fire
        onPickRef.current(hit.v)
      }
    }
    canvas.addEventListener('mousemove', onMove)
    canvas.addEventListener('mouseleave', onLeave)
    canvas.addEventListener('click', onClick)

    function drawHover(p) {
      ctx.globalCompositeOperation = 'source-over'
      ctx.globalAlpha = 1
      const name = (p.name || 'transaction').toString()
      const sub = (p.v.combined_verdict || p.status || '').toUpperCase()
      const shown = name.length > 30 ? name.slice(0, 29) + '…' : name
      ctx.font = '600 12.5px Inter, system-ui, sans-serif'
      const w1 = ctx.measureText(shown).width
      ctx.font = '11px Inter, system-ui, sans-serif'
      const w2 = ctx.measureText(sub).width
      const pad = 9, h = 40
      const w = Math.max(w1, w2) + pad * 2
      let bx = p.x + 16, by = p.y - h / 2
      if (bx + w > W - 6) bx = p.x - 16 - w
      by = Math.max(6, Math.min(H - h - 6, by))
      // highlight ring on the dot
      ctx.beginPath(); ctx.arc(p.x, p.y, 9, 0, Math.PI * 2)
      ctx.strokeStyle = 'rgba(255,255,255,0.92)'; ctx.lineWidth = 1.6; ctx.stroke()
      // label pill
      ctx.fillStyle = 'rgba(12,16,26,0.94)'
      roundRect(ctx, bx, by, w, h, 10); ctx.fill()
      ctx.strokeStyle = 'rgba(255,255,255,0.16)'; ctx.lineWidth = 1; ctx.stroke()
      ctx.textBaseline = 'alphabetic'
      ctx.fillStyle = '#e8edf6'; ctx.font = '600 12.5px Inter, system-ui, sans-serif'
      ctx.fillText(shown, bx + pad, by + 16)
      const c = COLORS[p.status] || [200, 200, 200]
      ctx.fillStyle = `rgb(${c[0]},${c[1]},${c[2]})`
      ctx.font = '11px Inter, system-ui, sans-serif'
      ctx.fillText(`${sub} · click to inspect`, bx + pad, by + 31)
    }

    let raf
    let last = performance.now()
    let ambientAcc = 0
    const reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches

    function frame(now) {
      const dt = Math.min(2.4, (now - last) / 16.67)
      last = now

      ctx.globalCompositeOperation = 'source-over'
      ctx.fillStyle = `rgba(${BG[0]},${BG[1]},${BG[2]},0.2)`
      ctx.fillRect(0, 0, W, H)

      if (ambient > 0) {
        ambientAcc += dt * 0.5 * intensity * ambient
        while (ambientAcc >= 1) { ambientAcc -= 1; spawn(AMBIENT[(Math.random() * AMBIENT.length) | 0]) }
      }

      // which dot is under the cursor (frozen so it's easy to click)
      hover = mouseX >= 0 ? nearest(mouseX, mouseY, HOVER_R) : null
      canvas.style.cursor = hover ? 'pointer' : 'default'

      ctx.globalCompositeOperation = 'lighter'
      for (let i = particles.length - 1; i >= 0; i--) {
        const p = particles[i]
        if (p.alpha < 1) p.alpha = Math.min(1, p.alpha + 0.09 * dt)

        if (p !== hover) {                 // frozen while hovered
          p.x += p.vx * dt
          p.y += p.vy * dt
          if (!p.decided && p.x >= p.decisionX) {
            p.decided = true
            if (p.status === 'blocked') { p.vy = 1.3 + Math.random() * 1.7; p.vx *= 0.42 }
            else if (p.status === 'review') { p.vy = -(0.9 + Math.random() * 1.3); p.vx *= 0.58 }
            else { p.vy *= 0.25 }
          }
          if (p.decided && p.status !== 'allowed') {
            p.vy += (p.status === 'blocked' ? 0.06 : 0.02) * dt
            p.life -= 0.0055 * dt
          }
        }

        const a = p.alpha * Math.max(0, p.life)
        const spr = sprites[p.status]
        const big = p === hover ? 1.6 : 1
        const glow = p.size * 7 * big
        ctx.globalAlpha = a * 0.85
        ctx.drawImage(spr, p.x - glow / 2, p.y - glow / 2, glow, glow)
        ctx.globalAlpha = a
        const core = p.size * big
        ctx.drawImage(spr, p.x - core, p.y - core, core * 2, core * 2)

        if (p.x > W + 36 || p.y > H + 36 || p.y < -36 || p.life <= 0) particles.splice(i, 1)
      }

      if (hover) drawHover(hover)
      ctx.globalAlpha = 1

      if (!reduce) raf = requestAnimationFrame(frame)
    }

    if (reduce) {
      if (ambient > 0) for (let i = 0; i < 60; i++) spawn(AMBIENT[(Math.random() * AMBIENT.length) | 0])
      frame(performance.now())
    } else {
      raf = requestAnimationFrame(frame)
    }

    return () => {
      cancelAnimationFrame(raf)
      ro.disconnect()
      window.removeEventListener('resize', resize)
      canvas.removeEventListener('mousemove', onMove)
      canvas.removeEventListener('mouseleave', onLeave)
      canvas.removeEventListener('click', onClick)
      off()
    }
  }, [intensity, ambient])

  return <canvas ref={ref} className="bg-canvas" aria-hidden="true" />
}
