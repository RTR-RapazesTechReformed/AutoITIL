import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { BarChart3, LayoutDashboard, KanbanSquare, UploadCloud, History, Users, DollarSign, LogOut } from 'lucide-react'
import ThemeToggle from '@/components/ThemeToggle'
import { useCurrentUser } from '@/components/RequireAuth'
import { clearToken } from '@/lib/auth'
import { cn } from '@/lib/utils'

const NAV_ITEMS = [
  { to: '/ingestao', label: 'Ingestão', icon: UploadCloud },
  { to: '/kanban', label: 'Kanban', icon: KanbanSquare },
  { to: '/operacao', label: 'Operação', icon: LayoutDashboard },
  { to: '/modelos', label: 'Modelos', icon: BarChart3 },
  { to: '/historico-uploads', label: 'Histórico', icon: History },
  { to: '/custos', label: 'Custos', icon: DollarSign },
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

function Layout() {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const isFullWidthPage = FULL_WIDTH_ROUTES.some((route) => pathname.startsWith(route))
  const usuario = useCurrentUser()
  const navItems = usuario.is_admin
    ? [...NAV_ITEMS, { to: '/admin/usuarios', label: 'Usuários', icon: Users }]
    : NAV_ITEMS

  function handleLogout() {
    clearToken()
    navigate('/login')
  }

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <aside className="sticky top-4 ml-4 flex h-[calc(100vh-2rem)] w-56 shrink-0 flex-col gap-1 rounded-2xl border bg-card p-3 shadow-sm">
        <div className="mb-2 flex items-center justify-between gap-1">
          <Link
            to="/"
            className="rounded-xl px-2.5 py-2 text-sm font-semibold hover:bg-accent hover:text-accent-foreground"
          >
            AutoITIL
          </Link>
          <ThemeToggle />
        </div>
        <nav className="flex flex-col gap-1">
          {navItems.map((item) => {
            const Icon = item.icon
            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-2.5 rounded-xl px-2.5 py-2 text-sm transition-colors',
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
        <button
          type="button"
          onClick={handleLogout}
          className="mt-auto flex items-center gap-2.5 rounded-xl px-2.5 py-2 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
        >
          <LogOut className="size-4 shrink-0" strokeWidth={2} aria-hidden="true" />
          Sair
        </button>
      </aside>
      <main className="min-w-0 flex-1 px-4 py-6 md:px-8">
        <div className={cn(!isFullWidthPage && 'mx-auto max-w-5xl')}>
          <Outlet />
        </div>
      </main>
    </div>
  )
}

export default Layout
