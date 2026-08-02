import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'

export function LandingPage() {
  return (
    <div className="relative flex min-h-svh flex-col overflow-hidden">
      <div aria-hidden className="pointer-events-none absolute inset-0">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_rgba(45,212,191,0.12),_transparent_55%),radial-gradient(ellipse_at_bottom_right,_rgba(245,197,66,0.08),_transparent_50%)]" />
        <div className="absolute -left-24 top-1/4 h-72 w-72 rounded-full bg-[var(--primary)]/15 blur-3xl motion-safe:animate-pulse" />
        <div className="absolute -right-16 bottom-1/3 h-80 w-80 rounded-full bg-[var(--accent)]/10 blur-3xl" />
        <div
          className="absolute inset-0 opacity-[0.035]"
          style={{
            backgroundImage:
              'linear-gradient(var(--border) 1px, transparent 1px), linear-gradient(90deg, var(--border) 1px, transparent 1px)',
            backgroundSize: '48px 48px',
          }}
        />
      </div>

      <main className="relative z-10 flex flex-1 flex-col items-center justify-center px-4 py-16 text-center">
        <p className="font-display text-6xl font-extrabold tracking-tight text-[#f0f4fa] sm:text-7xl md:text-8xl">
          Quiz<span className="text-[var(--primary)]">Arena</span>
        </p>
        <p className="mt-5 max-w-md text-base text-[var(--muted-foreground)] sm:text-lg">
          Host live quizzes with precision.
        </p>

        <div className="mt-12 flex w-full max-w-sm flex-col gap-3 sm:max-w-none sm:flex-row sm:justify-center">
          <Button asChild size="lg" className="h-12 min-w-[10.5rem] text-base">
            <Link to="/host/login">🎤 Host a Quiz</Link>
          </Button>
          <Button asChild size="lg" variant="secondary" className="h-12 min-w-[10.5rem] text-base">
            <Link to="/join">🎮 Join a Quiz</Link>
          </Button>
        </div>
      </main>
    </div>
  )
}
