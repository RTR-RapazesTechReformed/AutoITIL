import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ToastProvider } from '@/lib/toast'
import Usuarios from './Usuarios'

// useToast() (Task 5) exige um ToastProvider na árvore — sem ele lança.
// A brief original renderiza <Usuarios /> isolado; envolvemos aqui do
// mesmo jeito que Kanban.test.tsx faz para os demais consumidores de
// useToast.
function renderUsuarios() {
  return render(
    <ToastProvider>
      <Usuarios />
    </ToastProvider>,
  )
}

const { listUsersMock, createUserMock, updateUserMock, useCurrentUserMock } = vi.hoisted(() => ({
  listUsersMock: vi.fn(),
  createUserMock: vi.fn(),
  updateUserMock: vi.fn(),
  useCurrentUserMock: vi.fn(),
}))

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api')
  return {
    ...actual,
    listUsers: listUsersMock,
    createUser: createUserMock,
    updateUser: updateUserMock,
  }
})

vi.mock('@/components/RequireAuth', async () => {
  const actual = await vi.importActual<typeof import('@/components/RequireAuth')>(
    '@/components/RequireAuth',
  )
  return { ...actual, useCurrentUser: useCurrentUserMock }
})

beforeEach(() => {
  listUsersMock.mockReset()
  createUserMock.mockReset()
  updateUserMock.mockReset()
  useCurrentUserMock.mockReturnValue({ id: 1, email: 'admin@a.com', is_admin: true })
})

describe('Usuarios (admin)', () => {
  it('lista os usuários existentes', async () => {
    listUsersMock.mockResolvedValue([
      { id: 2, email: 'analista@a.com', is_admin: false, ativo: true },
    ])

    renderUsuarios()

    await waitFor(() => expect(screen.getByText('analista@a.com')).toBeInTheDocument())
  })

  it('cria um usuário novo e recarrega a lista', async () => {
    listUsersMock.mockResolvedValue([])
    createUserMock.mockResolvedValue({ id: 3, email: 'novo@a.com', is_admin: false, ativo: true })
    const user = userEvent.setup()

    renderUsuarios()
    await waitFor(() => expect(listUsersMock).toHaveBeenCalledTimes(1))

    await user.type(screen.getByLabelText('Email'), 'novo@a.com')
    await user.type(screen.getByLabelText('Senha'), 'senha-correta')
    await user.click(screen.getByRole('button', { name: 'Criar' }))

    await waitFor(() =>
      expect(createUserMock).toHaveBeenCalledWith({
        email: 'novo@a.com',
        senha: 'senha-correta',
        is_admin: false,
      }),
    )
    expect(listUsersMock).toHaveBeenCalledTimes(2)
  })

  it('mostra acesso restrito quando o usuário logado não é admin', () => {
    useCurrentUserMock.mockReturnValue({ id: 2, email: 'analista@a.com', is_admin: false })

    renderUsuarios()

    expect(screen.getByText('Acesso restrito a administradores.')).toBeInTheDocument()
  })
})
