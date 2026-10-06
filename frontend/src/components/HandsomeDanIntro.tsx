import { useEffect, useState } from 'react'

const SEEN_KEY = 'cc-dan-intro-seen'

// Paw prints left along Dan's route (positions as % of the viewport, delay in seconds).
const PAWS = [
  { x: 14, y: 30, delay: 0.5, turn: 60 },
  { x: 27, y: 44, delay: 0.9, turn: 80 },
  { x: 41, y: 62, delay: 1.3, turn: 100 },
  { x: 55, y: 70, delay: 1.7, turn: 70 },
  { x: 70, y: 58, delay: 2.1, turn: 20 },
  { x: 78, y: 40, delay: 2.5, turn: -20 },
]

function shouldPlay(): boolean {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return false
  try {
    return !sessionStorage.getItem(SEEN_KEY)
  } catch {
    return true // storage blocked: still play, just not remembered
  }
}

/**
 * A one-time intro on the Home page: Handsome Dan I flies in, explores the page, barks, and
 * flies off, leaving paw prints. Plays once per browser session, never blocks clicks, and is
 * skipped entirely for visitors who prefer reduced motion.
 */
export default function HandsomeDanIntro() {
  const [playing, setPlaying] = useState(shouldPlay)

  // Remember it played, so it only runs on the first Home visit of the session.
  useEffect(() => {
    if (!playing) return
    try {
      sessionStorage.setItem(SEEN_KEY, '1')
    } catch {
      // ignore
    }
  }, [playing])

  if (!playing) return null

  return (
    <div className="dan-intro" aria-hidden="true">
      {PAWS.map((paw, i) => (
        <span
          key={i}
          className="dan-paw"
          style={{ left: `${paw.x}vw`, top: `${paw.y}vh`, animationDelay: `${paw.delay}s`, rotate: `${paw.turn}deg` }}
        >
          🐾
        </span>
      ))}
      <div className="dan-flyer" onAnimationEnd={(e) => e.target === e.currentTarget && setPlaying(false)}>
        <div className="dan-face" />
        <span className="dan-bark">Woof! Boola boola!</span>
      </div>
    </div>
  )
}
