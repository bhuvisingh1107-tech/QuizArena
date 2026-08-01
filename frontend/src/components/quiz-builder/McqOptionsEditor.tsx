import { cn } from '@/lib/utils'
import type { AnswerOption } from '@/types/api'

export type BuilderQuestionKind = 'mcq' | 'true_false'

export interface DraftOption {
  id?: string
  text: string
  isCorrect: boolean
  sortOrder: number
}

const OPTION_LABELS = ['A', 'B', 'C', 'D'] as const

export function defaultMcqOptions(): DraftOption[] {
  return OPTION_LABELS.map((_, index) => ({
    text: '',
    isCorrect: index === 0,
    sortOrder: index,
  }))
}

export function defaultTrueFalseOptions(correct: 'True' | 'False' = 'True'): DraftOption[] {
  return [
    { text: 'True', isCorrect: correct === 'True', sortOrder: 0 },
    { text: 'False', isCorrect: correct === 'False', sortOrder: 1 },
  ]
}

export function inferQuestionKind(options: AnswerOption[]): BuilderQuestionKind {
  if (options.length === 2) {
    const texts = options.map((o) => o.text.trim().toLowerCase()).sort()
    if (texts[0] === 'false' && texts[1] === 'true') return 'true_false'
  }
  return 'mcq'
}

export function questionKindLabel(kind: BuilderQuestionKind, questionType?: string): string {
  if (kind === 'true_false') return 'True/False'
  if (questionType === 'Image') return 'Multiple Choice · Image'
  if (questionType === 'Audio') return 'Multiple Choice · Audio'
  return 'Multiple Choice'
}

export function optionLetter(index: number): string {
  return OPTION_LABELS[index] ?? String(index + 1)
}

interface McqOptionsEditorProps {
  kind: BuilderQuestionKind
  options: DraftOption[]
  allowMultipleCorrect: boolean
  onChange: (options: DraftOption[]) => void
  error?: string | null
}

export function McqOptionsEditor({
  kind,
  options,
  allowMultipleCorrect,
  onChange,
  error,
}: McqOptionsEditorProps) {
  if (kind === 'true_false') {
    const correct = options.find((o) => o.isCorrect)?.text === 'False' ? 'False' : 'True'
    return (
      <div className="space-y-3">
        <p className="text-sm font-medium text-[#f0f4fa]">Correct answer</p>
        <div className="flex gap-2">
          {(['True', 'False'] as const).map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => onChange(defaultTrueFalseOptions(value))}
              className={cn(
                'rounded-md border px-4 py-2 text-sm font-medium transition-colors',
                correct === value
                  ? 'border-[var(--primary)] bg-[var(--primary)]/15 text-[var(--primary)]'
                  : 'border-[var(--border)] text-[var(--muted-foreground)] hover:bg-[var(--secondary)]',
              )}
            >
              {value}
            </button>
          ))}
        </div>
        {error ? <p className="text-xs text-[var(--destructive)]">{error}</p> : null}
      </div>
    )
  }

  const setCorrect = (index: number, checked: boolean) => {
    if (allowMultipleCorrect) {
      onChange(
        options.map((opt, i) => (i === index ? { ...opt, isCorrect: checked } : opt)),
      )
      return
    }
    onChange(options.map((opt, i) => ({ ...opt, isCorrect: i === index })))
  }

  return (
    <div className="space-y-3">
      <p className="text-sm font-medium text-[#f0f4fa]">Options (A–D)</p>
      <ul className="space-y-2">
        {options.slice(0, 4).map((option, index) => (
          <li key={option.id ?? index} className="flex items-center gap-2">
            <span className="w-6 shrink-0 text-center text-sm font-semibold text-[var(--muted-foreground)]">
              {optionLetter(index)}
            </span>
            <input
              type={allowMultipleCorrect ? 'checkbox' : 'radio'}
              name="correct-option"
              checked={option.isCorrect}
              onChange={(e) => setCorrect(index, e.target.checked)}
              className="h-4 w-4 accent-[var(--primary)]"
              aria-label={`Mark option ${optionLetter(index)} correct`}
            />
            <input
              type="text"
              value={option.text}
              onChange={(e) =>
                onChange(
                  options.map((opt, i) =>
                    i === index ? { ...opt, text: e.target.value } : opt,
                  ),
                )
              }
              placeholder={`Option ${optionLetter(index)}`}
              className="flex h-10 w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm"
            />
          </li>
        ))}
      </ul>
      {error ? <p className="text-xs text-[var(--destructive)]">{error}</p> : null}
    </div>
  )
}
