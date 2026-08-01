import { useEffect, useRef, useState } from 'react'

import { cn } from '@/lib/utils'

interface AnimatedCounterProps {
  value: number
  className?: string
  'data-testid'?: string
}

export function AnimatedCounter({
  value,
  className,
  'data-testid': testId,
}: AnimatedCounterProps) {
  const [display, setDisplay] = useState(value)
  const [pulse, setPulse] = useState(false)
  const displayRef = useRef(value)
  const prevValueRef = useRef(value)

  useEffect(() => {
    displayRef.current = display
  }, [display])

  useEffect(() => {
    if (value === prevValueRef.current) return
    prevValueRef.current = value
    setPulse(true)
    const timeout = window.setTimeout(() => setPulse(false), 600)
    const start = displayRef.current
    const diff = value - start
    if (diff === 0) return () => window.clearTimeout(timeout)

    const steps = Math.min(Math.abs(diff), 12)
    const stepMs = 40
    let step = 0

    const interval = window.setInterval(() => {
      step += 1
      const next = Math.round(start + (diff * step) / steps)
      setDisplay(next)
      if (step >= steps) window.clearInterval(interval)
    }, stepMs)

    return () => {
      window.clearTimeout(timeout)
      window.clearInterval(interval)
    }
  }, [value])

  return (
    <span
      className={cn(
        'inline-block tabular-nums transition-transform duration-300',
        pulse && 'scale-110 text-[var(--accent)]',
        className,
      )}
      data-testid={testId}
    >
      {display}
    </span>
  )
}
