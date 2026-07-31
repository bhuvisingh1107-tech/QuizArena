import { PageHeader } from '@/components/shared/PageHeader'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useAuth } from '@/hooks/queries/useAuth'

export function SettingsPage() {
  const { admin } = useAuth()

  return (
    <div className="space-y-6">
      <PageHeader
        title="Settings"
        description="Administrator profile and platform configuration."
      />

      <Card className="max-w-xl">
        <CardHeader>
          <CardTitle>Administrator profile</CardTitle>
          <CardDescription>Loaded from GET /admin/me</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <div className="flex justify-between gap-4 border-b border-[var(--border)] py-2">
            <span className="text-[var(--muted-foreground)]">Username</span>
            <span className="font-medium text-[#f0f4fa]">{admin?.username ?? '—'}</span>
          </div>
          <div className="flex justify-between gap-4 border-b border-[var(--border)] py-2">
            <span className="text-[var(--muted-foreground)]">Role</span>
            <span className="font-medium text-[#f0f4fa]">{admin?.role ?? '—'}</span>
          </div>
          <div className="flex justify-between gap-4 py-2">
            <span className="text-[var(--muted-foreground)]">Admin ID</span>
            <span className="max-w-[60%] truncate font-mono text-xs text-[#f0f4fa]">
              {admin?.id ?? '—'}
            </span>
          </div>
        </CardContent>
      </Card>

      <Alert className="max-w-xl">
        <AlertTitle>Platform settings deferred</AlertTitle>
        <AlertDescription>
          Branding and platform configuration APIs are not available yet. This page will host those
          controls when the backend settings endpoints ship.
        </AlertDescription>
      </Alert>
    </div>
  )
}
