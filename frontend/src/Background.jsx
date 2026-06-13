import React, { useEffect, useRef } from 'react'
import { feed } from './feed.js'

// Each screened payment is a glowing particle that streams in from the left. At a
// "decision line" near the middle it resolves:
//   allowed (green)  → keeps flowing right and exits
//   review  (amber)  → lifts upward and fades
//   blocked (red)    → falls downward and fades
// Real verdicts from the live feed drive it; light ambient traffic keeps it alive between
// bursts. Rendered on a canvas with additive blending + motion-trails for a neon look.

const COLORS = {
  allowed: [40, 230, 140],
  review: [245, 195, 45],
  blocked: [244, 72, 86],
}
const BG = [7, 10, 18]

// ambient distribution roughly mirrors real traffic (~90% clear / 9% review / 1% block)
const AMBIENT = [
  ...Array(88).fill('allowed'),
  ...Array(9).fill('review'),
  ...Array(3).fill('blocked'),
]

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

export default function Background({ intensity = 1, ambient = 1 }) {
  const ref = useRef(null)

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
    const queue = []
    const MAX = 1600
    let W = 0, H = 0

    function resize() {
      W = canvas.clientWidth
      H = canvas.clientHeight
      canvas.width = Math.floor(W * dpr)
      canvas.height = Math.floor(H * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.fillStyle = `rgb(${BG[0]},${BG[1]},${BG[2]})`
      ctx.fillRect(0, 0, W, H)
    }
    resize()
    window.addEventListener('resize', resize)

    const off = feed.onVerdict((v) => queue.push(v.status || 'allowed'))

    function spawn(status) {
      if (particles.length >= MAX) return
      const speed = (W / 760) * (0.55 + Math.random() * 0.95) * intensity
      particles.push({
        status,
        x: -20,
        y: Math.random() * H,
        vx: speed,
        vy: (Math.random() - 0.5) * 0.2,
        size: 1.5 + Math.random() * 2.1,
        decided: false,
        decisionX: W * (0.4 + Math.random() * 0.24),
        alpha: 0,
        life: 1,
      })
    }

    let raf
    let last = performance.now()
    let ambientAcc = 0
    const reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches

    function frame(now) {
      const dt = Math.min(2.4, (now - last) / 16.67)
      last = now

      // translucent repaint → motion trails
      ctx.globalCompositeOperation = 'source-over'
      ctx.fillStyle = `rgba(${BG[0]},${BG[1]},${BG[2]},0.2)`
      ctx.fillRect(0, 0, W, H)

      // drain real verdicts (smoothed so a 50/s replay burst doesn't all appear at once)
      let budget = Math.max(2, Math.ceil(queue.length / 8))
      while (queue.length && budget-- > 0) spawn(queue.shift())

      // ambient filler
      ambientAcc += dt * 0.5 * intensity * ambient
      while (ambientAcc >= 1) {
        ambientAcc -= 1
        if (queue.length < 24) spawn(AMBIENT[(Math.random() * AMBIENT.length) | 0])
      }

      ctx.globalCompositeOperation = 'lighter'
      for (let i = particles.length - 1; i >= 0; i--) {
        const p = particles[i]
        if (p.alpha < 1) p.alpha = Math.min(1, p.alpha + 0.09 * dt)
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

        const a = p.alpha * Math.max(0, p.life)
        const spr = sprites[p.status]
        const glow = p.size * 7
        ctx.globalAlpha = a * 0.85
        ctx.drawImage(spr, p.x - glow / 2, p.y - glow / 2, glow, glow)
        ctx.globalAlpha = a
        ctx.drawImage(spr, p.x - p.size, p.y - p.size, p.size * 2, p.size * 2)

        if (p.x > W + 36 || p.y > H + 36 || p.y < -36 || p.life <= 0) particles.splice(i, 1)
      }
      ctx.globalAlpha = 1

      if (!reduce) raf = requestAnimationFrame(frame)
    }

    if (reduce) {
      // static-ish: seed a calm field once
      for (let i = 0; i < 60; i++) spawn(AMBIENT[(Math.random() * AMBIENT.length) | 0])
      frame(performance.now())
    } else {
      raf = requestAnimationFrame(frame)
    }

    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', resize)
      off()
    }
  }, [intensity, ambient])

  return <canvas ref={ref} className="bg-canvas" aria-hidden="true" />
}
