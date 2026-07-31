import { Trash2, Upload } from 'lucide-react'
import { useEffect, useState } from 'react'

import { EmptyState } from '@/components/shared/EmptyState'
import { PageHeader } from '@/components/shared/PageHeader'
import { Badge } from '@/components/ui/badge'
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useMediaMutations } from '@/hooks/queries/useMedia'
import { toastError, toastSuccess } from '@/lib/toast-helpers'
import type { MediaCategory, MediaFile } from '@/types/api'

const STORAGE_KEY = 'qa_admin_media_session'
const CATEGORIES: MediaCategory[] = [
  'question_image',
  'question_audio',
  'quiz_branding',
  'platform_branding',
]

function loadSessionMedia(): MediaFile[] {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as MediaFile[]
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function saveSessionMedia(items: MediaFile[]) {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(items))
  } catch {
    // ignore quota / private mode
  }
}

export function MediaPage() {
  const { uploadMedia, deleteMedia } = useMediaMutations()
  const [items, setItems] = useState<MediaFile[]>([])
  const [category, setCategory] = useState<MediaCategory>('question_image')
  const [quizId, setQuizId] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)

  useEffect(() => {
    setItems(loadSessionMedia())
  }, [])

  const persist = (next: MediaFile[]) => {
    setItems(next)
    saveSessionMedia(next)
  }

  const onUpload = async () => {
    if (!file) {
      toastError(new Error('Choose a file to upload'))
      return
    }
    setUploading(true)
    try {
      const media = await uploadMedia.mutateAsync({
        file,
        category,
        quizId: quizId.trim() || null,
      })
      persist([media, ...items.filter((m) => m.id !== media.id)])
      setFile(null)
      toastSuccess('Media uploaded')
    } catch (error) {
      toastError(error)
    } finally {
      setUploading(false)
    }
  }

  const onDelete = async (mediaId: string) => {
    if (!window.confirm('Delete this media file?')) return
    try {
      await deleteMedia.mutateAsync(mediaId)
      persist(items.filter((m) => m.id !== mediaId))
      toastSuccess('Media deleted')
    } catch (error) {
      toastError(error)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Media"
        description="Upload assets for questions and branding. There is no library list API yet — uploads in this session are tracked locally."
      />

      <Card>
        <CardHeader>
          <CardTitle>Upload</CardTitle>
          <CardDescription>
            Files attach to quizzes/questions via the question editor or by quiz ID here.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2 sm:col-span-2">
            <Label htmlFor="file">File</Label>
            <Input
              id="file"
              type="file"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </div>
          <div className="space-y-2">
            <Label>Category</Label>
            <Select value={category} onValueChange={(v) => setCategory(v as MediaCategory)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {CATEGORIES.map((c) => (
                  <SelectItem key={c} value={c}>
                    {c}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="quizId">Quiz ID (optional)</Label>
            <Input
              id="quizId"
              placeholder="UUID"
              value={quizId}
              onChange={(e) => setQuizId(e.target.value)}
            />
          </div>
          <div className="sm:col-span-2">
            <Button onClick={() => void onUpload()} disabled={uploading || !file}>
              <Upload className="h-4 w-4" />
              {uploading ? 'Uploading…' : 'Upload'}
            </Button>
          </div>
        </CardContent>
      </Card>

      {items.length === 0 ? (
        <EmptyState
          title="No uploads in this session"
          description="Uploaded media metadata is stored in sessionStorage until you refresh clear it. Attach images to questions from the question editor."
        />
      ) : (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)]/60">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>File</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>Size</TableHead>
                <TableHead>URL</TableHead>
                <TableHead className="w-12" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((media) => (
                <TableRow key={media.id}>
                  <TableCell className="font-medium text-[#f0f4fa]">
                    {media.originalFilename ?? media.id}
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary">{media.category}</Badge>
                  </TableCell>
                  <TableCell className="text-[var(--muted-foreground)]">
                    {(media.fileSize / 1024).toFixed(1)} KB
                  </TableCell>
                  <TableCell>
                    <a
                      href={media.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-[var(--primary)] hover:underline"
                    >
                      Open
                    </a>
                  </TableCell>
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="text-[var(--destructive)]"
                      onClick={() => void onDelete(media.id)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}
