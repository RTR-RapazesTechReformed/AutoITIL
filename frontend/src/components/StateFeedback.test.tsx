import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import StateFeedback from './StateFeedback'

describe('StateFeedback', () => {
  it('não renderiza nada quando loading e error estão ausentes', () => {
    const { container } = render(<StateFeedback />)
    expect(container).toBeEmptyDOMElement()
  })

  it('mostra o rótulo de loading com um spinner animado', () => {
    render(<StateFeedback loading loadingLabel="Processando..." />)

    expect(screen.getByText('Processando...')).toBeInTheDocument()
    // lucide-react renderiza <svg aria-hidden="true">, sem role acessível —
    // localiza pelo container e confere a classe de animação diretamente.
    const spinner = document.querySelector('svg')
    expect(spinner).toBeInTheDocument()
    expect(spinner).toHaveClass('motion-safe:animate-spin')
  })

  it('mostra a mensagem de erro e chama onRetry ao clicar em Tentar novamente', async () => {
    const onRetry = vi.fn()
    render(<StateFeedback error="Falha de rede" onRetry={onRetry} />)

    expect(screen.getByText(/Falha de rede/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /tentar novamente/i }))
    expect(onRetry).toHaveBeenCalledOnce()
  })

  it('não mostra botão de retry quando onRetry não é passado', () => {
    render(<StateFeedback error="Falha de rede" />)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
