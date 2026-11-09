import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'
import ToastViewport from '@/components/ToastViewport'
import { ToastProvider, useToast } from './toast'

function TriggerButton() {
  const { showToast } = useToast()
  return (
    <button type="button" onClick={() => showToast('Deu certo.', 'success')}>
      Disparar toast
    </button>
  )
}

describe('toast', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('mostra a mensagem ao chamar showToast e some sozinha depois do timeout', () => {
    render(
      <ToastProvider>
        <TriggerButton />
        <ToastViewport />
      </ToastProvider>,
    )

    act(() => {
      fireEvent.click(screen.getByRole('button', { name: 'Disparar toast' }))
    })
    expect(screen.getByText('Deu certo.')).toBeInTheDocument()

    act(() => {
      vi.advanceTimersByTime(4000)
    })
    expect(screen.queryByText('Deu certo.')).not.toBeInTheDocument()
  })

  it('lança erro se useToast for chamado fora do ToastProvider', () => {
    function Bare() {
      useToast()
      return null
    }
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    expect(() => render(<Bare />)).toThrow('useToast precisa ser usado dentro de um ToastProvider.')
    spy.mockRestore()
  })
})
