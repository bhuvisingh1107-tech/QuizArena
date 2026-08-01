import { memo, useCallback, useRef, type KeyboardEvent } from 'react'

import type { AnswerSubmitState, ParticipantLiveOption } from '@/types/api'
import { cn } from '@/lib/utils'

interface OptionListProps {
  options: ParticipantLiveOption[]
  selectedOptionIds: string[]
  allowMultiple?: boolean
  disabled?: boolean
  showCorrectness?: boolean
  submissionStatus?: AnswerSubmitState
  onChange: (optionIds: string[]) => void
  className?: string
}

export const OptionList = memo(function OptionList({
  options,
  selectedOptionIds,
  allowMultiple = false,
  disabled = false,
  showCorrectness = false,
  submissionStatus = 'idle',
  onChange,
  className,
}: OptionListProps) {
  const listRef = useRef<HTMLUListElement>(null)
  const locked =
    disabled ||
    submissionStatus === 'submitting' ||
    submissionStatus === 'submitted' ||
    submissionStatus === 'already_submitted'

  const toggle = useCallback(
    (id: string) => {
      if (locked) return
      if (allowMultiple) {
        const next = selectedOptionIds.includes(id)
          ? selectedOptionIds.filter((x) => x !== id)
          : [...selectedOptionIds, id]
        onChange(next)
        return
      }
      onChange(selectedOptionIds.includes(id) ? [] : [id])
    },
    [allowMultiple, locked, onChange, selectedOptionIds],
  )

  const onKeyDown = (event: KeyboardEvent<HTMLUListElement>) => {
    if (locked || options.length === 0) return
    const keys = ['ArrowDown', 'ArrowUp', 'Home', 'End', 'Enter', ' ']
    if (!keys.includes(event.key)) return
    event.preventDefault()

    const currentIndex = Math.max(
      0,
      options.findIndex((option) => selectedOptionIds.includes(option.id)),
    )
    let nextIndex = currentIndex
    if (event.key === 'ArrowDown') nextIndex = (currentIndex + 1) % options.length
    if (event.key === 'ArrowUp') nextIndex = (currentIndex - 1 + options.length) % options.length
    if (event.key === 'Home') nextIndex = 0
    if (event.key === 'End') nextIndex = options.length - 1

    const next = options[nextIndex]
    if (!next) return

    if (event.key === 'Enter' || event.key === ' ') {
      toggle(next.id)
      return
    }

    if (!allowMultiple) {
      onChange([next.id])
    }
    const button = listRef.current?.querySelectorAll<HTMLButtonElement>('button[role="option"]')[
      nextIndex
    ]
    button?.focus()
  }

  return (
    <ul
      ref={listRef}
      className={cn('space-y-3', className)}
      role="listbox"
      aria-label="Answer options"
      aria-multiselectable={allowMultiple}
      tabIndex={locked ? -1 : 0}
      onKeyDown={onKeyDown}
    >
      {options.length === 0 ? (
        <li className="rounded-xl border border-dashed border-[var(--border)] px-4 py-8 text-center text-sm text-[var(--muted-foreground)]">
          Waiting for answer choices…
        </li>
      ) : null}
      {options.map((option, index) => {
        const selected = selectedOptionIds.includes(option.id)
        const letter = String.fromCharCode(65 + index)
        const correct = showCorrectness && option.isCorrect === true
        const incorrect = showCorrectness && selected && option.isCorrect === false

        return (
          <li key={option.id}>
            <button
              type="button"
              role="option"
              aria-selected={selected}
              disabled={locked}
              onClick={() => toggle(option.id)}
              className={cn(
                'flex min-h-14 w-full items-start gap-3 rounded-xl border px-4 py-3 text-left transition-colors',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]',
                selected
                  ? 'border-[var(--primary)] bg-[var(--primary)]/15'
                  : 'border-[var(--border)] bg-[var(--card)]/70 hover:border-[var(--primary)]/50',
                correct && 'border-[var(--color-success)] bg-[var(--color-success)]/15',
                incorrect && 'border-[var(--destructive)] bg-[var(--destructive)]/10',
                locked && 'cursor-not-allowed opacity-80',
              )}
            >
              <span
                className={cn(
                  'mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg font-display text-sm font-bold',
                  selected
                    ? 'bg-[var(--primary)] text-[var(--primary-foreground)]'
                    : 'bg-[var(--secondary)] text-[var(--muted-foreground)]',
                  correct && 'bg-[var(--color-success)] text-[var(--color-ink)]',
                )}
              >
                {letter}
              </span>
              <span className="pt-1 text-base leading-snug text-[var(--heading)]">{option.text}</span>
            </button>
          </li>
        )
      })}
    </ul>
  )
})
