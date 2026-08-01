import { Archive, Copy, Radio, Trash2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { BuilderStepper, type BuilderStep } from '@/components/quiz-builder/BuilderStepper'
import {
  QuizDetailsStep,
  quizDetailsToInput,
  type QuizDetailsFormValues,
} from '@/components/quiz-builder/QuizDetailsStep'
import { QuestionsStep } from '@/components/quiz-builder/QuestionsStep'
import { ReviewStep } from '@/components/quiz-builder/ReviewStep'
import { ConfirmDialog } from '@/components/shared/ConfirmDialog'
import { ErrorState } from '@/components/shared/ErrorState'
import { LoadingState } from '@/components/shared/LoadingState'
import { PageHeader } from '@/components/shared/PageHeader'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { Button } from '@/components/ui/button'
import { useLiveRoomMutations } from '@/hooks/queries/useLiveRoomMutations'
import { useQuiz } from '@/hooks/queries/useQuiz'
import { useQuizMutations } from '@/hooks/queries/useQuizMutations'
import { useSectionMutations, useSections } from '@/hooks/queries/useSections'
import { apiPost } from '@/lib/api-client'
import { toastError, toastSuccess } from '@/lib/toast-helpers'

function parseStep(raw: string | null): BuilderStep {
  const n = Number(raw)
  if (n === 2 || n === 3) return n
  return 1
}

export function QuizBuilderPage() {
  const { quizId: routeQuizId } = useParams()
  const isNew = !routeQuizId || routeQuizId === 'new'
  const quizId = isNew ? undefined : routeQuizId
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const step = isNew ? 1 : parseStep(searchParams.get('step'))
  const [archiveConfirm, setArchiveConfirm] = useState(false)
  const [archiveLoading, setArchiveLoading] = useState(false)
  const [selectedSectionId, setSelectedSectionId] = useState<string | null>(null)

  const quizQuery = useQuiz(quizId, Boolean(quizId))
  const sectionsQuery = useSections(quizId, Boolean(quizId))
  const sectionMutations = useSectionMutations(quizId ?? '')
  const { createQuiz, updateQuiz, deleteQuiz, archiveQuiz, duplicateQuiz, restoreQuiz } =
    useQuizMutations()
  const { createRoom } = useLiveRoomMutations()

  const sections = useMemo(
    () =>
      [...(sectionsQuery.data?.items ?? [])].sort((a, b) => a.sortOrder - b.sortOrder),
    [sectionsQuery.data],
  )

  const section = useMemo(
    () => sections.find((item) => item.id === selectedSectionId) ?? sections[0] ?? null,
    [sections, selectedSectionId],
  )

  useEffect(() => {
    if (sections.length === 0) {
      setSelectedSectionId(null)
      return
    }
    if (!selectedSectionId || !sections.some((item) => item.id === selectedSectionId)) {
      setSelectedSectionId(sections[0].id)
    }
  }, [sections, selectedSectionId])

  const setStep = (next: BuilderStep) => {
    if (isNew) return
    setSearchParams({ step: String(next) }, { replace: true })
  }

  const onSaveDetails = async (values: QuizDetailsFormValues) => {
    const input = quizDetailsToInput(values)
    try {
      if (isNew || !quizId) {
        const quiz = await createQuiz.mutateAsync(input)
        // Ensure a default section exists for the Questions step.
        await apiPost(`/quizzes/${quiz.id}/sections`, {
          name: 'Section 1',
          sortOrder: 0,
        })
        toastSuccess('Quiz created')
        navigate(`/admin/quizzes/${quiz.id}?step=2`, { replace: true })
        return
      }
      await updateQuiz.mutateAsync({ quizId, input })
      toastSuccess('Quiz saved')
      setStep(2)
    } catch (error) {
      toastError(error)
      throw error
    }
  }

  const onAddSection = async () => {
    if (!quizId) return
    const nextIndex = sections.length + 1
    try {
      const created = await sectionMutations.createSection.mutateAsync({
        name: `Section ${nextIndex}`,
        sortOrder: sections.length,
      })
      setSelectedSectionId(created.id)
      toastSuccess('Section created')
    } catch (error) {
      toastError(error)
    }
  }

  const onRenameSection = async (target: { id: string; name: string }) => {
    if (!quizId) return
    const nextName = window.prompt('Section name', target.name)?.trim()
    if (!nextName || nextName === target.name) return
    try {
      await sectionMutations.updateSection.mutateAsync({
        sectionId: target.id,
        input: { name: nextName },
      })
      toastSuccess('Section renamed')
    } catch (error) {
      toastError(error)
    }
  }

  const hostLiveRoom = async () => {
    if (!quizId) return
    try {
      const room = await createRoom.mutateAsync({ quizId })
      toastSuccess('Live room created')
      navigate(`/admin/live-rooms/${room.id}`)
    } catch (error) {
      toastError(error)
    }
  }

  if (!isNew && quizQuery.isLoading) {
    return <LoadingState label="Loading quiz…" />
  }

  if (!isNew && (quizQuery.isError || !quizQuery.data)) {
    return (
      <ErrorState
        message={quizQuery.error instanceof Error ? quizQuery.error.message : 'Quiz not found'}
        onRetry={() => void quizQuery.refetch()}
      />
    )
  }

  const quiz = quizQuery.data

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader
        title={isNew ? 'Create quiz' : (quiz?.title ?? 'Quiz builder')}
        description={
          isNew
            ? 'Step through details, questions, and review to publish.'
            : 'Edit details, questions, and publish when ready.'
        }
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {quiz ? <StatusBadge status={quiz.status} /> : null}
            {quiz?.status === 'Ready' ? (
              <Button
                variant="secondary"
                size="sm"
                disabled={createRoom.isPending}
                onClick={() => void hostLiveRoom()}
              >
                <Radio className="h-4 w-4" />
                {createRoom.isPending ? 'Creating room…' : 'Host live room'}
              </Button>
            ) : null}
            {quizId && quiz ? (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    void duplicateQuiz
                      .mutateAsync(quizId)
                      .then((copy) => {
                        toastSuccess('Duplicated')
                        navigate(`/admin/quizzes/${copy.id}`)
                      })
                      .catch(toastError)
                  }
                >
                  <Copy className="h-4 w-4" />
                  Duplicate
                </Button>
                {quiz.status === 'Archived' ? (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      void restoreQuiz
                        .mutateAsync(quizId)
                        .then(() => {
                          toastSuccess('Restored')
                          void quizQuery.refetch()
                        })
                        .catch(toastError)
                    }
                  >
                    Restore
                  </Button>
                ) : quiz.status === 'Ready' ? (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setArchiveConfirm(true)}
                  >
                    <Archive className="h-4 w-4" />
                    Archive
                  </Button>
                ) : null}
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => {
                    if (!window.confirm('Delete this quiz?')) return
                    void deleteQuiz
                      .mutateAsync({ quizId })
                      .then(() => {
                        toastSuccess('Deleted')
                        navigate('/admin/quizzes')
                      })
                      .catch(toastError)
                  }}
                >
                  <Trash2 className="h-4 w-4" />
                  Delete
                </Button>
              </>
            ) : null}
            <Button asChild variant="ghost" size="sm">
              <Link to="/admin/quizzes">Cancel</Link>
            </Button>
          </div>
        }
      />

      <BuilderStepper
        currentStep={step}
        onStepChange={setStep}
        allowJump={!isNew}
        maxReachableStep={isNew ? 1 : 3}
      />

      {step === 1 ? (
        <QuizDetailsStep
          quiz={quiz}
          submitting={createQuiz.isPending || updateQuiz.isPending}
          onSave={onSaveDetails}
          submitLabel={isNew ? 'Save & Continue' : 'Save & Continue'}
        />
      ) : null}

      {step === 2 && quizId ? (
        <QuestionsStep
          quizId={quizId}
          sections={sections}
          section={section}
          selectedSectionId={selectedSectionId}
          onSelectSection={setSelectedSectionId}
          onAddSection={() => void onAddSection()}
          onRenameSection={(target) => void onRenameSection(target)}
          sectionsLoading={sectionsQuery.isLoading}
          sectionsError={sectionsQuery.isError}
          onRetrySections={() => void sectionsQuery.refetch()}
          onContinue={() => setStep(3)}
          addingSection={sectionMutations.createSection.isPending}
        />
      ) : null}

      {step === 3 && quiz ? (
        <ReviewStep
          quiz={quiz}
          sections={sections}
          onBack={(s) => {
            void quizQuery.refetch()
            setStep(s)
          }}
          onPublished={() => void quizQuery.refetch()}
        />
      ) : null}

      <ConfirmDialog
        open={archiveConfirm}
        onOpenChange={setArchiveConfirm}
        title="Archive quiz?"
        description={
          quiz
            ? `Archive “${quiz.title}”? It will no longer be available for new live sessions.`
            : undefined
        }
        confirmLabel="Archive"
        loading={archiveLoading}
        onConfirm={async () => {
          if (!quizId) return
          setArchiveLoading(true)
          try {
            await archiveQuiz.mutateAsync(quizId)
            toastSuccess('Archived')
            setArchiveConfirm(false)
            void quizQuery.refetch()
          } catch (error) {
            toastError(error)
          } finally {
            setArchiveLoading(false)
          }
        }}
      />
    </div>
  )
}
