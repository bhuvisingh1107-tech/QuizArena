import { ApiError } from '@/lib/api-client'
import { toast } from '@/components/ui/toast'

export function toastError(error: unknown, fallback = 'Something went wrong') {
  if (error instanceof ApiError) {
    toast({
      title: error.code,
      description: error.message,
      variant: 'destructive',
    })
    return
  }
  toast({
    title: 'Error',
    description: error instanceof Error ? error.message : fallback,
    variant: 'destructive',
  })
}

export function toastSuccess(title: string, description?: string) {
  toast({ title, description, variant: 'success' })
}
