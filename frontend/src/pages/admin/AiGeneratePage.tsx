import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { FileUp, Sparkles, UploadCloud } from 'lucide-react'

import { PageHeader } from '@/components/shared/PageHeader'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useAiGenerationMutations, useAiJobsQuery } from '@/hooks/queries/useAiGeneration'
import { toastError, toastSuccess } from '@/lib/toast-helpers'
import type { AiDifficulty, AiGenerationMode, AiQuestionKind } from '@/types/ai-generation'
import { cn } from '@/lib/utils'

const KIND_OPTIONS: { value: AiQuestionKind; label: string }[] = [
  { value: 'mcq', label: 'MCQ' },
  { value: 'multiple_correct', label: 'Multiple correct' },
  { value: 'true_false', label: 'True / False' },
  { value: 'fill_blank', label: 'Fill in blank' },
]

const ACCEPT =
  '.pdf,.ppt,.pptx,.doc,.docx,.png,.jpg,.jpeg,.mp4,.txt,application/pdf,text/plain,image/*,video/mp4'

export function AiGeneratePage() {
  const navigate = useNavigate()
  const mutations = useAiGenerationMutations()
  const history = useAiJobsQuery()

  const [mode, setMode] = useState<AiGenerationMode>('topic')
  const [topic, setTopic] = useState('')
  const [title, setTitle] = useState('')
  const [questionCount, setQuestionCount] = useState(12)
  const [difficulty, setDifficulty] = useState<AiDifficulty>('mixed')
  const [kinds, setKinds] = useState<AiQuestionKind[]>(['mcq'])
  const [file, setFile] = useState<File | null>(null)
  const [dragOver, setDragOver] = useState(false)

  const busy = mutations.createDocument.isPending || mutations.createTopic.isPending || mutations.upload.isPending

  const toggleKind = (kind: AiQuestionKind) => {
    setKinds((prev) => {
      if (prev.includes(kind)) {
        const next = prev.filter((k) => k !== kind)
        return next.length ? next : prev
      }
      return [...prev, kind]
    })
  }

  const onGenerate = async () => {
    try {
      if (mode === 'topic') {
        if (topic.trim().length < 2) {
          toastError(new Error('Enter a topic'))
          return
        }
        const job = await mutations.createTopic.mutateAsync({
          topic: topic.trim(),
          title: title.trim() || undefined,
          questionCount,
          difficulty,
          questionKinds: kinds,
          language: 'en',
        })
        toastSuccess('Generation started')
        navigate(`/admin/quizzes/ai/${job.id}`)
        return
      }

      if (!file) {
        toastError(new Error('Choose a file to upload'))
        return
      }
      const job = await mutations.createDocument.mutateAsync({
        title: title.trim() || undefined,
        questionCount,
        difficulty,
        questionKinds: kinds,
        language: 'en',
      })
      await mutations.upload.mutateAsync({ jobId: job.id, file })
      toastSuccess('Upload received — generating quiz')
      navigate(`/admin/quizzes/ai/${job.id}`)
    } catch (error) {
      toastError(error)
    }
  }

  const recent = useMemo(() => history.data?.items?.slice(0, 8) ?? [], [history.data])

  return (
    <div className="space-y-8">
      <PageHeader
        title="Generate with AI"
        description="Create quizzes from study material or a topic — section-aware, reviewable, production-ready."
        actions={
          <Button asChild variant="outline">
            <Link to="/admin/quizzes">Back to quizzes</Link>
          </Button>
        }
      />

      <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <Card className="overflow-hidden border-[var(--border)] bg-gradient-to-br from-[var(--card)] to-[var(--secondary)]/40">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 font-display text-2xl">
              <Sparkles className="h-5 w-5 text-[var(--accent)]" />
              AI settings
            </CardTitle>
            <CardDescription>
              Choose a generation mode, tune difficulty and question types, then generate.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="grid gap-3 sm:grid-cols-2">
              <button
                type="button"
                onClick={() => setMode('topic')}
                className={cn(
                  'rounded-xl border px-4 py-4 text-left transition',
                  mode === 'topic'
                    ? 'border-[var(--primary)] bg-[var(--primary)]/10'
                    : 'border-[var(--border)] hover:border-[var(--primary)]/40',
                )}
              >
                <p className="font-semibold text-[var(--heading)]">Topic</p>
                <p className="mt-1 text-sm text-[var(--muted-foreground)]">
                  Generate from trusted educational sources.
                </p>
              </button>
              <button
                type="button"
                onClick={() => setMode('document')}
                className={cn(
                  'rounded-xl border px-4 py-4 text-left transition',
                  mode === 'document'
                    ? 'border-[var(--primary)] bg-[var(--primary)]/10'
                    : 'border-[var(--border)] hover:border-[var(--primary)]/40',
                )}
              >
                <p className="font-semibold text-[var(--heading)]">Upload material</p>
                <p className="mt-1 text-sm text-[var(--muted-foreground)]">
                  PDF, PPT, DOCX, images, video, TXT.
                </p>
              </button>
            </div>

            {mode === 'topic' ? (
              <div className="space-y-2">
                <Label htmlFor="topic">Topic</Label>
                <Input
                  id="topic"
                  placeholder="e.g. Vector Calculus, Operating Systems"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                />
              </div>
            ) : (
              <div
                onDragOver={(e) => {
                  e.preventDefault()
                  setDragOver(true)
                }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(e) => {
                  e.preventDefault()
                  setDragOver(false)
                  const next = e.dataTransfer.files?.[0]
                  if (next) setFile(next)
                }}
                className={cn(
                  'flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed px-6 py-10 text-center transition',
                  dragOver
                    ? 'border-[var(--primary)] bg-[var(--primary)]/10'
                    : 'border-[var(--border)] bg-[var(--card)]/60',
                )}
              >
                <UploadCloud className="h-8 w-8 text-[var(--muted-foreground)]" />
                <div>
                  <p className="font-medium text-[var(--heading)]">Drag & drop study material</p>
                  <p className="text-sm text-[var(--muted-foreground)]">
                    PDF, PPT/PPTX, DOC/DOCX, PNG/JPG, MP4, TXT
                  </p>
                </div>
                <Label
                  htmlFor="ai-file"
                  className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm"
                >
                  <FileUp className="h-4 w-4" />
                  Choose file
                </Label>
                <input
                  id="ai-file"
                  type="file"
                  accept={ACCEPT}
                  className="sr-only"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                />
                {file ? (
                  <p className="text-sm text-[var(--primary)]">{file.name}</p>
                ) : null}
              </div>
            )}

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="title">Quiz title (optional)</Label>
                <Input
                  id="title"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Auto-detected if empty"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="count">Question count</Label>
                <Input
                  id="count"
                  type="number"
                  min={1}
                  max={100}
                  value={questionCount}
                  onChange={(e) => setQuestionCount(Number(e.target.value) || 1)}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label>Difficulty</Label>
              <Select value={difficulty} onValueChange={(v) => setDifficulty(v as AiDifficulty)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="easy">Easy</SelectItem>
                  <SelectItem value="medium">Medium</SelectItem>
                  <SelectItem value="hard">Hard</SelectItem>
                  <SelectItem value="mixed">Mixed</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Question types</Label>
              <div className="flex flex-wrap gap-2">
                {KIND_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => toggleKind(opt.value)}
                    className={cn(
                      'rounded-full border px-3 py-1.5 text-sm transition',
                      kinds.includes(opt.value)
                        ? 'border-[var(--accent)] bg-[var(--accent)]/15 text-[var(--heading)]'
                        : 'border-[var(--border)] text-[var(--muted-foreground)]',
                    )}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            <Button type="button" size="lg" className="w-full sm:w-auto" disabled={busy} onClick={() => void onGenerate()}>
              {busy ? 'Starting…' : 'Generate quiz'}
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Generation history</CardTitle>
            <CardDescription>Retry or open recent AI jobs.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {recent.length === 0 ? (
              <p className="text-sm text-[var(--muted-foreground)]">No jobs yet.</p>
            ) : (
              recent.map((job) => (
                <Link
                  key={job.id}
                  to={`/admin/quizzes/ai/${job.id}`}
                  className="block rounded-lg border border-[var(--border)] px-3 py-3 transition hover:border-[var(--primary)]/50"
                >
                  <div className="flex items-center justify-between gap-2">
                    <p className="truncate font-medium text-[var(--heading)]">
                      {job.title || job.topic || 'Untitled job'}
                    </p>
                    <span className="text-xs uppercase tracking-wide text-[var(--muted-foreground)]">
                      {job.status}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-[var(--muted-foreground)]">
                    {job.mode} · {job.progressPercent}%
                  </p>
                </Link>
              ))
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
