import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ThemeToggle from './ThemeToggle'

function mockMatchMedia(matches: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches,
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  })) as unknown as typeof window.matchMedia
}

describe('ThemeToggle', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.classList.remove('dark')
    mockMatchMedia(false)
  })

  it('mostra o rótulo pra ativar tema escuro quando o tema atual é claro', () => {
    render(<ThemeToggle />)

    expect(screen.getByRole('button', { name: /ativar tema escuro/i })).toBeInTheDocument()
  })

  it('ativa a classe .dark e inverte o rótulo ao clicar', async () => {
    render(<ThemeToggle />)

    await userEvent.click(screen.getByRole('button', { name: /ativar tema escuro/i }))

    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(screen.getByRole('button', { name: /ativar tema claro/i })).toBeInTheDocument()
  })

  it('clicar de novo volta pro tema claro', async () => {
    render(<ThemeToggle />)

    await userEvent.click(screen.getByRole('button', { name: /ativar tema escuro/i }))
    await userEvent.click(screen.getByRole('button', { name: /ativar tema claro/i }))

    expect(document.documentElement.classList.contains('dark')).toBe(false)
    expect(screen.getByRole('button', { name: /ativar tema escuro/i })).toBeInTheDocument()
  })
})
