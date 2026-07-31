import {
  ClipboardList,
  LayoutDashboard,
  LogOut,
  Radio,
  Settings,
  Trophy,
  Image as ImageIcon,
  Menu,
  X,
} from 'lucide-react'
import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { useAuth } from '@/hooks/queries/useAuth'
import { cn } from '@/lib/utils'

const navItems = [
  { to: '/admin/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/admin/quizzes', label: 'Quizzes', icon: ClipboardList },
  { to: '/admin/live-rooms', label: 'Live Rooms', icon: Radio },
  { to: '/admin/results', label: 'Results', icon: Trophy },
  { to: '/admin/media', label: 'Media', icon: ImageIcon },
  { to: '/admin/settings', label: 'Settings', icon: Settings },
]

export function AdminLayout() {
  const { admin, logout } = useAuth()
  const navigate = useNavigate()
  const [mobileOpen, setMobileOpen] = useState(false)

  const handleLogout = async () => {
    await logout()
    navigate('/admin/login', { replace: true })
  }

  const nav = (
    <nav className="flex flex-1 flex-col gap-1 px-3 py-4">
      {navItems.map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          onClick={() => setMobileOpen(false)}
          className={({ isActive }) =>
            cn(
              'flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors',
              isActive
                ? 'bg-[var(--primary)]/15 text-[var(--primary)]'
                : 'text-[var(--muted-foreground)] hover:bg-[var(--secondary)] hover:text-[var(--foreground)]',
            )
          }
        >
          <Icon className="h-4 w-4 shrink-0" />
          {label}
        </NavLink>
      ))}
    </nav>
  )

  return (
    <div className="flex min-h-svh">
      <aside className="hidden w-64 shrink-0 flex-col border-r border-[var(--border)] bg-[var(--color-ink-elevated)]/90 backdrop-blur md:flex">
        <div className="px-5 py-6">
          <p className="font-display text-2xl font-extrabold tracking-tight text-[#f0f4fa]">
            Quiz<span className="text-[var(--primary)]">Arena</span>
          </p>
          <p className="mt-1 text-xs uppercase tracking-[0.18em] text-[var(--muted-foreground)]">
            Admin Console
          </p>
        </div>
        <Separator />
        {nav}
        <div className="mt-auto border-t border-[var(--border)] p-4">
          <p className="mb-3 truncate text-sm text-[var(--muted-foreground)]">
            Signed in as{' '}
            <span className="font-medium text-[var(--foreground)]">{admin?.username}</span>
          </p>
          <Button variant="outline" className="w-full" onClick={() => void handleLogout()}>
            <LogOut className="h-4 w-4" />
            Logout
          </Button>
        </div>
      </aside>

      {mobileOpen ? (
        <div className="fixed inset-0 z-40 flex md:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-black/60"
            aria-label="Close menu"
            onClick={() => setMobileOpen(false)}
          />
          <aside className="relative z-10 flex h-full w-72 flex-col bg-[var(--color-ink-elevated)] shadow-xl">
            <div className="flex items-center justify-between px-5 py-5">
              <p className="font-display text-xl font-extrabold">
                Quiz<span className="text-[var(--primary)]">Arena</span>
              </p>
              <Button variant="ghost" size="icon" onClick={() => setMobileOpen(false)}>
                <X className="h-5 w-5" />
              </Button>
            </div>
            <Separator />
            {nav}
            <div className="mt-auto border-t border-[var(--border)] p-4">
              <Button variant="outline" className="w-full" onClick={() => void handleLogout()}>
                <LogOut className="h-4 w-4" />
                Logout
              </Button>
            </div>
          </aside>
        </div>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-[var(--border)] bg-[var(--color-ink-elevated)]/70 px-4 py-3 backdrop-blur md:hidden">
          <Button variant="ghost" size="icon" onClick={() => setMobileOpen(true)}>
            <Menu className="h-5 w-5" />
          </Button>
          <p className="font-display text-lg font-bold">
            Quiz<span className="text-[var(--primary)]">Arena</span>
          </p>
        </header>
        <main className="flex-1 overflow-auto px-4 py-6 sm:px-6 lg:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
