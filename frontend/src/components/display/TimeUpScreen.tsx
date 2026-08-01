import { cn } from '@/lib/utils'

interface TimeUpScreenProps {
  className?: string
}

export function TimeUpScreen({ className }: TimeUpScreenProps) {
  return (
    <section
      className={cn(
        'flex flex-1 flex-col items-center justify-center gap-8 text-center',
        className,
      )}
      aria-label="Time is up"
      data-testid="time-up-screen"
    >
      <div className="relative">
        <div
          className="absolute inset-0 animate-ping rounded-full bg-[var(--accent)]/20"
          aria-hidden
        />
        <div className="relative flex h-32 w-32 items-center justify-center rounded-full border-4 border-[var(--accent)]/60 bg-[var(--accent)]/10 lg:h-40 lg:w-40">
          <span className="font-display text-5xl font-extrabold text-[var(--accent)] lg:text-6xl">
            ⏱
          </span>
        </div>
      </div>

      <div className="space-y-3">
        <h1 className="font-display text-5xl font-extrabold text-[#f0f4fa] sm:text-6xl lg:text-7xl">
          Time&apos;s Up!
        </h1>
        <p className="text-lg text-[var(--muted-foreground)] lg:text-2xl">
          Calculating scores…
        </p>
      </div>

      <div className="flex gap-2" aria-hidden>
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="h-3 w-3 animate-bounce rounded-full bg-[var(--primary)]"
            style={{ animationDelay: `${i * 150}ms` }}
          />
        ))}
      </div>
    </section>
  )
}
