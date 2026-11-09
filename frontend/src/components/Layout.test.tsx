import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import Layout from './Layout'

const { clearTokenMock } = vi.hoisted(() => ({ clearTokenMock: vi.fn() }))

vi.mock('@/lib/auth', () => ({ clearToken: clearTokenMock }))

// Layout (Task 7) consome useCurrentUser() — que só funciona dentro de uma
// árvore montada por RequireAuth. Como este teste não é sobre autenticação
// nem sobre o link condicional de admin, mockamos o hook diretamente (mesmo
// padrão usado em Usuarios.test.tsx) em vez de montar RequireAuth de verdade
// (o que exigiria mockar a chamada de rede de getCurrentUser aqui também).
const { useCurrentUserMock } = vi.hoisted(() => ({
  useCurrentUserMock: vi.fn(),
}))

vi.mock('@/components/RequireAuth', async () => {
  const actual = await vi.importActual<typeof import('@/components/RequireAuth')>(
    '@/components/RequireAuth',
  )
  return { ...actual, useCurrentUser: useCurrentUserMock }
})

beforeEach(() => {
  useCurrentUserMock.mockReturnValue({ id: 1, email: 'usuario@a.com', is_admin: false })
  clearTokenMock.mockClear()
})

// useTheme (via ThemeToggle, renderizado dentro de Layout) chama
// window.matchMedia — não implementado por padrão no jsdom — e
// localStorage.getItem, que nesta versão de jsdom/Node também lança
// (mesma incompatibilidade de ambiente documentada nas 7 falhas
// pré-existentes de ThemeToggle.test.tsx/theme.test.ts). Como este teste
// não é sobre tema, um stub mínimo em memória evita o erro sem precisar
// consertar o ambiente aqui.
function mockMatchMedia(matches: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches,
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  })) as unknown as typeof window.matchMedia
}

function mockLocalStorage() {
  const store = new Map<string, string>()
  window.localStorage = {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => store.set(key, value),
    removeItem: (key: string) => store.delete(key),
    clear: () => store.clear(),
    key: () => null,
    length: 0,
  } as unknown as Storage
}

function renderAt(path: string) {
  mockMatchMedia(false)
  mockLocalStorage()
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/kanban" element={<div>conteúdo kanban</div>} />
          <Route path="/operacao" element={<div>conteúdo operação</div>} />
        </Route>
        <Route path="/login" element={<div>tela de login</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('Layout', () => {
  // Regressão: o Kanban precisa da largura cheia do <main> pra caber as
  // colunas lado a lado (estilo Trello) — o teto mx-auto max-w-5xl
  // (pensado pras outras telas) espremia o board e o scroll horizontal
  // "engolia" as colunas da esquerda ao rolar pra ver as da direita.
  it('não limita a largura do conteúdo na página do Kanban', () => {
    renderAt('/kanban')

    const content = screen.getByText('conteúdo kanban')
    expect(content.parentElement).not.toHaveClass('max-w-5xl')
  })

  it('mantém o limite de largura mx-auto max-w-5xl nas demais páginas', () => {
    renderAt('/operacao')

    const content = screen.getByText('conteúdo operação')
    expect(content.parentElement).toHaveClass('mx-auto', 'max-w-5xl')
  })

  it('"Sair" limpa o token salvo e volta pra tela de login', async () => {
    renderAt('/operacao')

    await userEvent.click(screen.getByRole('button', { name: 'Sair' }))

    expect(clearTokenMock).toHaveBeenCalledOnce()
    expect(screen.getByText('tela de login')).toBeInTheDocument()
  })
})
