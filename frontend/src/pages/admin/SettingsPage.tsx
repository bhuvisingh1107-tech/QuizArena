import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useNavigate } from 'react-router-dom'
import { z } from 'zod'

import { ConfirmDialog } from '@/components/shared/ConfirmDialog'
import { PageHeader } from '@/components/shared/PageHeader'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { useAuth } from '@/hooks/queries/useAuth'
import { useChangePassword } from '@/hooks/queries/useChangePassword'
import {
  getStoredAdminTheme,
  setAdminTheme,
} from '@/lib/admin-theme'
import { clearToken, getExpiresAt } from '@/lib/auth-token'
import { toastError, toastSuccess } from '@/lib/toast-helpers'
import { PASSWORD_POLICY_HINT, strongPasswordSchema } from '@/schemas/password'
import type { AdminTheme } from '@/types/api'

const passwordSchema = z
  .object({
    currentPassword: z.string().min(1, 'Current password is required'),
    newPassword: strongPasswordSchema,
    confirmPassword: z.string().min(1, 'Confirm your new password'),
  })
  .refine((data) => data.newPassword === data.confirmPassword, {
    message: 'Passwords do not match',
    path: ['confirmPassword'],
  })

type PasswordForm = z.infer<typeof passwordSchema>

export function SettingsPage() {
  const { admin, logout } = useAuth()
  const navigate = useNavigate()
  const changePassword = useChangePassword()
  const [theme, setTheme] = useState<AdminTheme>(() => getStoredAdminTheme())
  const [logoutOpen, setLogoutOpen] = useState(false)
  const [clearOpen, setClearOpen] = useState(false)
  const [busy, setBusy] = useState(false)

  const form = useForm<PasswordForm>({
    resolver: zodResolver(passwordSchema),
    defaultValues: {
      currentPassword: '',
      newPassword: '',
      confirmPassword: '',
    },
  })

  const expiresAt = getExpiresAt()

  const onSubmit = form.handleSubmit(async (values) => {
    try {
      await changePassword.mutateAsync({
        currentPassword: values.currentPassword,
        newPassword: values.newPassword,
      })
      toastSuccess('Password changed')
      form.reset()
    } catch (error) {
      toastError(error)
    }
  })

  const toggleTheme = (checked: boolean) => {
    const next: AdminTheme = checked ? 'dark' : 'light'
    setTheme(next)
    setAdminTheme(next)
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Profile"
        description="Host profile, security, and preferences."
      />

      <Card className="max-w-xl">
        <CardHeader>
          <CardTitle>Host profile</CardTitle>
          <CardDescription>Your signed-in host account</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <div className="flex justify-between gap-4 border-b border-[var(--border)] py-2">
            <span className="text-[var(--muted-foreground)]">Name</span>
            <span className="font-medium text-[var(--heading)]">{admin?.name || '—'}</span>
          </div>
          <div className="flex justify-between gap-4 border-b border-[var(--border)] py-2">
            <span className="text-[var(--muted-foreground)]">Username</span>
            <span className="font-medium text-[var(--heading)]">{admin?.username ?? '—'}</span>
          </div>
          <div className="flex justify-between gap-4 border-b border-[var(--border)] py-2">
            <span className="text-[var(--muted-foreground)]">Email</span>
            <span className="font-medium text-[var(--heading)]">{admin?.email || '—'}</span>
          </div>
          <div className="flex justify-between gap-4 border-b border-[var(--border)] py-2">
            <span className="text-[var(--muted-foreground)]">Role</span>
            <span className="font-medium text-[var(--heading)]">{admin?.role ?? '—'}</span>
          </div>
          <div className="flex justify-between gap-4 py-2">
            <span className="text-[var(--muted-foreground)]">Account ID</span>
            <span className="max-w-[60%] truncate font-mono text-xs text-[var(--heading)]">
              {admin?.id ?? '—'}
            </span>
          </div>
        </CardContent>
      </Card>

      <Card className="max-w-xl">
        <CardHeader>
          <CardTitle>Change password</CardTitle>
          <CardDescription>{PASSWORD_POLICY_HINT}</CardDescription>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={onSubmit} noValidate>
            <div className="space-y-2">
              <Label htmlFor="currentPassword">Current password</Label>
              <Input
                id="currentPassword"
                type="password"
                autoComplete="current-password"
                {...form.register('currentPassword')}
              />
              {form.formState.errors.currentPassword ? (
                <p className="text-xs text-[var(--destructive)]">
                  {form.formState.errors.currentPassword.message}
                </p>
              ) : null}
            </div>
            <div className="space-y-2">
              <Label htmlFor="newPassword">New password</Label>
              <Input
                id="newPassword"
                type="password"
                autoComplete="new-password"
                {...form.register('newPassword')}
              />
              {form.formState.errors.newPassword ? (
                <p className="text-xs text-[var(--destructive)]">
                  {form.formState.errors.newPassword.message}
                </p>
              ) : null}
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirmPassword">Confirm new password</Label>
              <Input
                id="confirmPassword"
                type="password"
                autoComplete="new-password"
                {...form.register('confirmPassword')}
              />
              {form.formState.errors.confirmPassword ? (
                <p className="text-xs text-[var(--destructive)]">
                  {form.formState.errors.confirmPassword.message}
                </p>
              ) : null}
            </div>
            <Button type="submit" disabled={changePassword.isPending}>
              {changePassword.isPending ? 'Saving…' : 'Update password'}
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card className="max-w-xl">
        <CardHeader>
          <CardTitle>Appearance</CardTitle>
          <CardDescription>Choose light or dark for the host console</CardDescription>
        </CardHeader>
        <CardContent className="flex items-center justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-[var(--heading)]">Dark theme</p>
            <p className="text-xs text-[var(--muted-foreground)]">
              Currently: {theme === 'dark' ? 'Dark' : 'Light'}
            </p>
          </div>
          <Switch
            checked={theme === 'dark'}
            onCheckedChange={toggleTheme}
            aria-label="Toggle dark theme"
          />
        </CardContent>
      </Card>

      <Card className="max-w-xl">
        <CardHeader>
          <CardTitle>Session</CardTitle>
          <CardDescription>When your signed-in session will expire</CardDescription>
        </CardHeader>
        <CardContent className="text-sm">
          <div className="flex justify-between gap-4 py-2">
            <span className="text-[var(--muted-foreground)]">Expires at</span>
            <span className="font-medium text-[var(--heading)]">
              {expiresAt ? new Date(expiresAt).toLocaleString() : 'Unknown'}
            </span>
          </div>
        </CardContent>
      </Card>

      <Card className="max-w-xl border-[var(--destructive)]/40">
        <CardHeader>
          <CardTitle className="text-[var(--destructive)]">Danger zone</CardTitle>
          <CardDescription>Sign out or clear the local admin session</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => setLogoutOpen(true)}>
            Logout
          </Button>
          <Button variant="destructive" onClick={() => setClearOpen(true)}>
            Clear local session
          </Button>
        </CardContent>
      </Card>

      <ConfirmDialog
        open={logoutOpen}
        onOpenChange={setLogoutOpen}
        title="Log out?"
        description="You will need to sign in again to access the admin console."
        confirmLabel="Logout"
        loading={busy}
        onConfirm={async () => {
          setBusy(true)
          try {
            await logout()
            navigate('/host/login', { replace: true })
          } finally {
            setBusy(false)
            setLogoutOpen(false)
          }
        }}
      />

      <ConfirmDialog
        open={clearOpen}
        onOpenChange={setClearOpen}
        title="Clear local session?"
        description="Removes the stored JWT from this browser without calling the logout API."
        confirmLabel="Clear session"
        variant="destructive"
        onConfirm={() => {
          clearToken()
          toastSuccess('Local session cleared')
          setClearOpen(false)
          navigate('/host/login', { replace: true })
          window.location.reload()
        }}
      />
    </div>
  )
}
