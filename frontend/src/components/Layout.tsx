import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Dialog as DialogPrimitive } from 'radix-ui'
import {
  BarChart3,
  LayoutDashboard,
  KanbanSquare,
  UploadCloud,
  History,
  Users,
  LogOut,
  Menu,
  X,
  type LucideIcon,
} from 'lucide-react'
import ThemeToggle from '@/components/ThemeToggle'
import { useCurrentUser } from '@/components/RequireAuth'
import { clearToken } from '@/lib/auth'
import { cn } from '@/lib/utils'

type NavItem = { to: string; label: string; icon: LucideIcon }

const NAV_ITEMS: NavItem[] = [
  { to: '/ingestao', label: 'Ingestão', icon: UploadCloud },
  { to: '/kanban', label: 'Kanban', icon: KanbanSquare },
  { to: '/operacao', label: 'Operação', icon: LayoutDashboard },
  { to: '/modelos', label: 'Modelos', icon: BarChart3 },
  { to: '/historico-uploads', label: 'Histórico', icon: History },
]

// V2 — Direção A "Pastel Flutuante": a navegação
// migrou da pílula horizontal pra uma barra lateral flutuante — mesmo
// vocabulário (bg-card, shadow-sm, cantos bem arredondados), orientação
// diferente. Referência estrutural: sidebar com bloco de identidade no
// topo + lista de itens com ícone, sem o agrupamento "Inboxes" do
// original — aqui não há um segundo nível de conteúdo real a agrupar.

// Regra de largura do <main>: o container casa com o tipo de conteúdo da
// página, não é uma largura única pra tudo.
// - Formulários/wizards (Ingestão) e dashboards de cards/gráficos em grid
//   fixo (Dashboard, Métricas) ficam em mx-auto max-w-5xl — largura
//   contida é boa prática de UX pra esse tipo de conteúdo (linha de
//   leitura curta em forms; grids fixos só ganhariam espaço vazio dentro
//   dos cards se alargados sem redesenhar o grid junto).
// - Boards com colunas fluidas que crescem pra preencher o espaço
//   (Kanban, `flex-1` nas raias) precisam de largura cheia — o mesmo
//   motivo pelo qual Trello/Linear/Notion não centralizam boards num
//   container estreito. Menos largura = menos colunas visíveis por vez =
//   mais scroll escondendo conteúdo.
// Uma página nova entra na lista de FULL_WIDTH_ROUTES abaixo só se for
// desse segundo tipo (board/tabela densa que se beneficia de esticar).
const FULL_WIDTH_ROUTES = ['/kanban']

// Responsividade: abaixo de `lg` (1024px) a barra lateral não cabe ao lado
// do conteúdo — 224px fixos numa tela de 360px deixavam ~100px pro miolo.
// O corte é em `lg`, não em `md`: com a lateral aberta em 768px o conteúdo
// ficaria com ~460px, largura de celular, mas com as variantes `sm:`/`md:`
// dos grids das páginas já ativas (elas olham a viewport, não o container).
// Abaixo do corte a lateral vira uma gaveta (mesmo vocabulário visual),
// aberta por um botão numa barra superior fixa.
const DESKTOP_QUERY = '(min-width: 64rem)'

function NavList({ items, onNavigate }: { items: NavItem[]; onNavigate?: () => void }) {
  return (
    <nav className="flex flex-col gap-1">
      {items.map((item) => {
        const Icon = item.icon
        return (
          <NavLink
            key={item.to}
            to={item.to}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                // min-h-11 (44px) só na gaveta mobile: alvo de toque confortável.
                'flex min-h-11 items-center gap-2.5 rounded-xl px-2.5 py-2 text-sm transition-colors lg:min-h-0',
                isActive
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
              )
            }
          >
            <Icon className="size-4 shrink-0" strokeWidth={2} aria-hidden="true" />
            {item.label}
          </NavLink>
        )
      })}
    </nav>
  )
}

function LogoutButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="mt-auto flex min-h-11 items-center gap-2.5 rounded-xl px-2.5 py-2 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground lg:min-h-0"
    >
      <LogOut className="size-4 shrink-0" strokeWidth={2} aria-hidden="true" />
      Sair
    </button>
  )
}

function Layout() {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const isFullWidthPage = FULL_WIDTH_ROUTES.some((route) => pathname.startsWith(route))
  const usuario = useCurrentUser()
  const navItems = usuario.is_admin
    ? [...NAV_ITEMS, { to: '/admin/usuarios', label: 'Usuários', icon: Users }]
    : NAV_ITEMS
  const [menuOpen, setMenuOpen] = useState(false)

  // Se a janela cresce até o layout de desktop com a gaveta aberta (girar um
  // tablet, redimensionar o navegador), fecha — senão o conteúdo dela some
  // via CSS mas o bloqueio de scroll e o foco preso do Dialog continuam.
  useEffect(() => {
    const query = window.matchMedia?.(DESKTOP_QUERY)
    if (!query) return
    const handleChange = (event: MediaQueryListEvent) => {
      if (event.matches) setMenuOpen(false)
    }
    query.addEventListener('change', handleChange)
    return () => query.removeEventListener('change', handleChange)
  }, [])

  function handleLogout() {
    setMenuOpen(false)
    clearToken()
    navigate('/login')
  }

  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground lg:flex-row">
      {/* Barra superior — só abaixo de lg. */}
      <header className="sticky top-0 z-40 flex h-14 shrink-0 items-center gap-1 border-b bg-background/90 px-2 backdrop-blur lg:hidden">
        <DialogPrimitive.Root open={menuOpen} onOpenChange={setMenuOpen}>
          <DialogPrimitive.Trigger asChild>
            <button
              type="button"
              aria-label="Abrir menu"
              className="flex size-10 items-center justify-center rounded-xl text-foreground hover:bg-accent hover:text-accent-foreground"
            >
              <Menu className="size-5" strokeWidth={2} aria-hidden="true" />
            </button>
          </DialogPrimitive.Trigger>
          <DialogPrimitive.Portal>
            <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/50 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 lg:hidden" />
            <DialogPrimitive.Content
              aria-describedby={undefined}
              className="fixed inset-y-0 left-0 z-50 flex w-72 max-w-[85vw] flex-col gap-1 overflow-y-auto rounded-r-2xl border-r bg-card p-3 shadow-lg outline-none data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:slide-out-to-left data-[state=open]:slide-in-from-left lg:hidden"
            >
              <div className="mb-2 flex items-center justify-between gap-1">
                <DialogPrimitive.Title className="sr-only">Menu de navegação</DialogPrimitive.Title>
                <Link
                  to="/"
                  onClick={() => setMenuOpen(false)}
                  className="rounded-xl px-2.5 py-2 text-sm font-semibold hover:bg-accent hover:text-accent-foreground"
                >
                  AutoITIL
                </Link>
                <DialogPrimitive.Close
                  aria-label="Fechar menu"
                  className="flex size-10 items-center justify-center rounded-xl text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                >
                  <X className="size-5" strokeWidth={2} aria-hidden="true" />
                </DialogPrimitive.Close>
              </div>
              <NavList items={navItems} onNavigate={() => setMenuOpen(false)} />
              <LogoutButton onClick={handleLogout} />
            </DialogPrimitive.Content>
          </DialogPrimitive.Portal>
        </DialogPrimitive.Root>
        <Link to="/" className="rounded-xl px-2 py-2 text-sm font-semibold">
          AutoITIL
        </Link>
        <ThemeToggle className="ml-auto size-10" />
      </header>

      {/* Barra lateral flutuante — de lg pra cima. */}
      <aside className="sticky top-4 ml-4 hidden h-[calc(100vh-2rem)] w-56 shrink-0 flex-col gap-1 rounded-2xl border bg-card p-3 shadow-sm lg:flex">
        <div className="mb-2 flex items-center justify-between gap-1">
          <Link
            to="/"
            className="rounded-xl px-2.5 py-2 text-sm font-semibold hover:bg-accent hover:text-accent-foreground"
          >
            AutoITIL
          </Link>
          <ThemeToggle />
        </div>
        <NavList items={navItems} />
        <LogoutButton onClick={handleLogout} />
      </aside>
      <main className="min-w-0 flex-1 px-4 py-5 md:px-8 md:py-6">
        <div className={cn(!isFullWidthPage && 'mx-auto max-w-5xl')}>
          <Outlet />
        </div>
      </main>
    </div>
  )
}

export default Layout
