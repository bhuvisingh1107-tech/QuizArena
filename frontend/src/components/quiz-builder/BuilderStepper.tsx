import { cn } from '@/lib/utils'

export type BuilderStep = 1 | 2 | 3

const STEPS: Array<{ id: BuilderStep; label: string }> = [
  { id: 1, label: 'Details' },
  { id: 2, label: 'Questions' },
  { id: 3, label: 'Review' },
]

interface BuilderStepperProps {
  currentStep: BuilderStep
  onStepChange?: (step: BuilderStep) => void
  /** When false, steps 2–3 are not clickable (new quiz before create). */
  allowJump?: boolean
  maxReachableStep?: BuilderStep
}

export function BuilderStepper({
  currentStep,
  onStepChange,
  allowJump = true,
  maxReachableStep = 3,
}: BuilderStepperProps) {
  return (
    <ol className="flex flex-wrap items-center gap-2 sm:gap-0">
      {STEPS.map((step, index) => {
        const isActive = step.id === currentStep
        const isComplete = step.id < currentStep
        const canJump =
          allowJump &&
          Boolean(onStepChange) &&
          step.id !== currentStep &&
          step.id <= maxReachableStep

        return (
          <li key={step.id} className="flex items-center">
            {index > 0 ? (
              <div
                className={cn(
                  'mx-2 hidden h-px w-8 sm:block',
                  isComplete || isActive ? 'bg-[var(--primary)]' : 'bg-[var(--border)]',
                )}
                aria-hidden
              />
            ) : null}
            <button
              type="button"
              disabled={!canJump}
              onClick={() => canJump && onStepChange?.(step.id)}
              className={cn(
                'flex items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors',
                isActive && 'bg-[var(--primary)]/15 text-[var(--primary)]',
                isComplete && !isActive && 'text-[var(--foreground)]',
                !isActive && !isComplete && 'text-[var(--muted-foreground)]',
                canJump && 'hover:bg-[var(--secondary)] cursor-pointer',
                !canJump && 'cursor-default',
              )}
            >
              <span
                className={cn(
                  'flex h-7 w-7 items-center justify-center rounded-full border text-xs font-semibold',
                  isActive &&
                    'border-[var(--primary)] bg-[var(--primary)] text-[var(--primary-foreground)]',
                  isComplete &&
                    !isActive &&
                    'border-[var(--primary)]/60 bg-[var(--primary)]/20 text-[var(--primary)]',
                  !isActive &&
                    !isComplete &&
                    'border-[var(--border)] bg-transparent text-[var(--muted-foreground)]',
                )}
              >
                {step.id}
              </span>
              <span className="font-medium">{step.label}</span>
            </button>
          </li>
        )
      })}
    </ol>
  )
}
