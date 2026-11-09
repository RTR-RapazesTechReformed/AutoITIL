import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import RequireAuth from './RequireAuth'
import { setToken } from '@/lib/auth'

const { getCurrentUserMock } = vi.hoisted(() => ({ getCurrentUserMock: vi.fn() }))

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api')
  return { ...actual, getCurrentUser: getCurrentUserMock }
})

beforeEach(() => {
  getCurrentUserMock.mockReset()
  localStorage.clear()
})

function renderWithGuard() {
  return render(
    <MemoryRouter initialEntries={['/protegida']}>
      <Routes>
        <Route path="/login" element={<div>Página de login</div>} />
        <Route element={<RequireAuth />}>
          <Route path="/protegida" element={<div>Conteúdo protegido</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
}

describe('RequireAuth', () => {
  it('redireciona para /login quando não há token', async () => {
    renderWithGuard()
    await waitFor(() => expect(screen.getByText('Página de login')).toBeInTheDocument())
  })

  it('renderiza o conteúdo protegido quando o token é válido', async () => {
    setToken('token-valido')
    getCurrentUserMock.mockResolvedValue({ id: 1, email: 'a@a.com', is_admin: false })

    renderWithGuard()

    await waitFor(() => expect(screen.getByText('Conteúdo protegido')).toBeInTheDocument())
  })

  it('redireciona para /login quando o token salvo é rejeitado pelo backend', async () => {
    setToken('token-expirado')
    getCurrentUserMock.mockRejectedValue(new Error('401'))

    renderWithGuard()

    await waitFor(() => expect(screen.getByText('Página de login')).toBeInTheDocument())
  })
})
