import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import Login from './Login'

const { loginMock } = vi.hoisted(() => ({ loginMock: vi.fn() }))

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api')
  return { ...actual, login: loginMock }
})

// useTheme (via ThemeToggle, renderizado dentro de Login desde o
// split-screen com branding) chama window.matchMedia — não implementado
// por padrão no jsdom. Mesmo stub usado em Layout.test.tsx.
function mockMatchMedia(matches: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches,
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  })) as unknown as typeof window.matchMedia
}

beforeEach(() => {
  loginMock.mockReset()
  localStorage.clear()
  mockMatchMedia(false)
})

describe('Login', () => {
  it('salva o token e navega em caso de sucesso', async () => {
    loginMock.mockResolvedValue({
      access_token: 'token-novo',
      usuario: { id: 1, email: 'a@a.com', is_admin: false },
    })
    const user = userEvent.setup()

    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>,
    )

    await user.type(screen.getByLabelText('Email'), 'a@a.com')
    await user.type(screen.getByLabelText('Senha'), 'senha-correta')
    await user.click(screen.getByRole('button', { name: 'Entrar' }))

    await waitFor(() => expect(localStorage.getItem('autoitil-auth-token')).toBe('token-novo'))
  })

  it('mostra mensagem de erro e não salva token quando a credencial é inválida', async () => {
    const { ApiRequestError } = await import('@/lib/api')
    loginMock.mockRejectedValue(
      new ApiRequestError(401, { code: 'INVALID_CREDENTIALS', message: 'Email ou senha inválidos.' }),
    )
    const user = userEvent.setup()

    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>,
    )

    await user.type(screen.getByLabelText('Email'), 'a@a.com')
    await user.type(screen.getByLabelText('Senha'), 'senha-errada')
    await user.click(screen.getByRole('button', { name: 'Entrar' }))

    await waitFor(() => expect(screen.getByText('Email ou senha inválidos.')).toBeInTheDocument())
    expect(localStorage.getItem('autoitil-auth-token')).toBeNull()
  })
})
