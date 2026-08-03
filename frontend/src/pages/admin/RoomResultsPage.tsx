import { Download, Printer } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { DataTable } from '@/components/shared/DataTable'
import { ErrorState } from '@/components/shared/ErrorState'
import { LoadingState } from '@/components/shared/LoadingState'
import { PageHeader } from '@/components/shared/PageHeader'
import { StatCard } from '@/components/shared/StatCard'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { TableCell, TableHead, TableRow } from '@/components/ui/table'
import {
  downloadRoomResults,
  useRoomResults,
} from '@/hooks/queries/useRoomResults'
import { toastError, toastSuccess } from '@/lib/toast-helpers'
import { cn } from '@/lib/utils'

export function RoomResultsPage() {
  const { roomId = '' } = useParams()
  const results = useRoomResults(roomId)
  const [exporting, setExporting] = useState(false)

  if (results.isLoading) return <LoadingState label="Loading results…" />

  if (results.isError || !results.data) {
    return (
      <ErrorState
        message={
          results.error instanceof Error ? results.error.message : 'Results not available'
        }
        onRetry={() => void results.refetch()}
      />
    )
  }

  const { room, summary, leaderboard, podium, questionAnalytics, sectionAnalytics } =
    results.data
  const podiumEntries = podium.entries.slice(0, 3)

  const handleExport = async () => {
    setExporting(true)
    try {
      await downloadRoomResults(roomId, 'xlsx')
      toastSuccess('Excel downloaded')
    } catch (error) {
      toastError(error)
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="print-results space-y-6">
      <PageHeader
        className="no-print"
        title={room.quizTitleSnapshot}
        description={`Results for room ${room.roomCode}`}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge state={room.state} />
            <Button
              size="sm"
              variant="secondary"
              disabled={exporting}
              onClick={() => void handleExport()}
            >
              <Download className="h-4 w-4" />
              {exporting ? 'Exporting…' : 'Export Excel'}
            </Button>
            <Button size="sm" variant="outline" onClick={() => window.print()}>
              <Printer className="h-4 w-4" />
              Print / PDF
            </Button>
            <Button asChild variant="outline" size="sm">
              <Link to="/admin/results">Back</Link>
            </Button>
          </div>
        }
      />

      <div className="mb-2 hidden print:block">
        <h1 className="font-display text-2xl font-bold">{room.quizTitleSnapshot}</h1>
        <p className="text-sm">
          Room {room.roomCode}
          {room.completedAt ? ` · Completed ${new Date(room.completedAt).toLocaleString()}` : ''}
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Participants" value={summary.participantCount} />
        <StatCard
          label="Average score"
          value={summary.averageScore.toFixed(1)}
          valueClassName="text-[var(--primary)]"
        />
        <StatCard
          label="Average accuracy"
          value={`${summary.averageAccuracyPercent.toFixed(1)}%`}
        />
        <StatCard label="Questions" value={summary.totalQuestions} />
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {[0, 1, 2].map((index) => {
          const entry = podiumEntries[index]
          return (
            <Card key={index} className={index === 0 ? 'border-[var(--accent)]/50' : undefined}>
              <CardHeader>
                <CardDescription>#{index + 1}</CardDescription>
                <CardTitle className="text-xl">{entry?.displayName ?? '—'}</CardTitle>
              </CardHeader>
              <CardContent className="text-2xl font-semibold text-[var(--primary)]">
                {entry?.score ?? '—'}
              </CardContent>
            </Card>
          )
        })}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Leaderboard</CardTitle>
          <CardDescription>Final rankings for this session</CardDescription>
        </CardHeader>
        <CardContent>
          <DataTable
            empty={leaderboard.length === 0}
            emptyTitle="No leaderboard data"
            emptyDescription="No scored participants for this room."
            columns={
              <>
                <TableHead>Rank</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Score</TableHead>
                <TableHead>Correct</TableHead>
                <TableHead>Incorrect</TableHead>
                <TableHead>Unanswered</TableHead>
                <TableHead>Streak</TableHead>
              </>
            }
          >
            {leaderboard.map((entry) => (
              <TableRow key={entry.participantId}>
                <TableCell>{entry.rank}</TableCell>
                <TableCell className="font-medium text-[var(--heading)]">
                  {entry.displayName}
                </TableCell>
                <TableCell>{entry.score}</TableCell>
                <TableCell>{entry.totalCorrect}</TableCell>
                <TableCell>{entry.totalIncorrect}</TableCell>
                <TableCell>{entry.unansweredCount}</TableCell>
                <TableCell>{entry.streak}</TableCell>
              </TableRow>
            ))}
          </DataTable>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Section analytics</CardTitle>
        </CardHeader>
        <CardContent>
          <DataTable
            empty={sectionAnalytics.length === 0}
            emptyTitle="No section analytics"
            columns={
              <>
                <TableHead>Section</TableHead>
                <TableHead>Questions</TableHead>
                <TableHead>Avg score</TableHead>
              </>
            }
          >
            {sectionAnalytics.map((section) => (
              <TableRow key={section.sectionId}>
                <TableCell className="font-medium text-[var(--heading)]">{section.name}</TableCell>
                <TableCell>{section.questionCount}</TableCell>
                <TableCell>{section.averageScore.toFixed(1)}</TableCell>
              </TableRow>
            ))}
          </DataTable>
        </CardContent>
      </Card>

      <div className="space-y-4">
        <h2 className="font-display text-xl font-semibold">Question analytics</h2>
        {questionAnalytics.length === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">No question analytics available.</p>
        ) : (
          questionAnalytics.map((q) => {
            const maxSelected = Math.max(
              1,
              ...q.optionDistribution.map((o) => o.selectedCount),
            )
            return (
              <Card key={q.questionId}>
                <CardHeader>
                  <CardDescription>
                    Q{q.questionIndex + 1} · {q.sectionName} · {q.accuracyPercent.toFixed(0)}%
                    accuracy
                  </CardDescription>
                  <CardTitle className="text-base">
                    {q.promptText ?? `Question ${q.questionIndex + 1}`}
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <p className="text-xs text-[var(--muted-foreground)]">
                    Submitted {q.submissionCount} · Correct {q.correctCount} · Incorrect{' '}
                    {q.incorrectCount} · Unanswered {q.unansweredCount}
                  </p>
                  <div className="space-y-2">
                    {q.optionDistribution.map((option) => (
                      <div key={option.optionId} className="space-y-1">
                        <div className="flex justify-between gap-2 text-xs">
                          <span
                            className={cn(
                              option.isCorrect && 'font-medium text-[var(--color-success)]',
                            )}
                          >
                            {option.isCorrect ? '✓ ' : ''}
                            {option.text}
                          </span>
                          <span className="text-[var(--muted-foreground)]">
                            {option.selectedCount}
                          </span>
                        </div>
                        <div className="h-2 overflow-hidden rounded-full bg-[var(--secondary)]">
                          <div
                            className={cn(
                              'h-full rounded-full',
                              option.isCorrect
                                ? 'bg-[var(--color-success)]'
                                : 'bg-[var(--primary)]/70',
                            )}
                            style={{
                              width: `${(option.selectedCount / maxSelected) * 100}%`,
                            }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )
          })
        )}
      </div>
    </div>
  )
}
