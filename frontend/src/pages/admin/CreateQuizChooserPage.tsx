import { FilePenLine, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'

import { PageHeader } from '@/components/shared/PageHeader'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

/**
 * Create Quiz entry: Manual builder vs AI generation.
 * Path: /admin/quizzes/new
 */
export function CreateQuizChooserPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <PageHeader
        title="Create quiz"
        description="Build manually, or generate a full draft from study material or a topic."
        actions={
          <Button asChild variant="outline">
            <Link to="/admin/quizzes">Back to quizzes</Link>
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2">
        <Link
          to="/admin/quizzes/ai"
          className="group rounded-2xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
        >
          <Card className="h-full border-[var(--border)] transition group-hover:border-[var(--primary)] group-hover:bg-[var(--primary)]/5">
            <CardHeader>
              <div className="mb-2 flex h-11 w-11 items-center justify-center rounded-xl bg-[var(--primary)]/15 text-[var(--primary)]">
                <Sparkles className="h-5 w-5" />
              </div>
              <CardTitle className="font-display text-xl">Generate with AI</CardTitle>
              <CardDescription>
                Upload PDF/PPT/DOCX/images/video, or enter a topic. Review section-wise questions,
                then save as a draft.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <span className="text-sm font-medium text-[var(--primary)]">Start AI generation →</span>
            </CardContent>
          </Card>
        </Link>

        <Link
          to="/admin/quizzes/new/manual"
          className="group rounded-2xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
        >
          <Card className="h-full border-[var(--border)] transition group-hover:border-[var(--primary)] group-hover:bg-[var(--primary)]/5">
            <CardHeader>
              <div className="mb-2 flex h-11 w-11 items-center justify-center rounded-xl bg-[var(--secondary)] text-[var(--heading)]">
                <FilePenLine className="h-5 w-5" />
              </div>
              <CardTitle className="font-display text-xl">Create manually</CardTitle>
              <CardDescription>
                Write the quiz yourself — details, sections, questions, and options in the builder.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <span className="text-sm font-medium text-[var(--heading)]">Open quiz builder →</span>
            </CardContent>
          </Card>
        </Link>
      </div>
    </div>
  )
}
