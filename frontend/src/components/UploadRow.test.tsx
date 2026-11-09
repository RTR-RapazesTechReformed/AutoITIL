import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import UploadRow from './UploadRow'

describe('UploadRow', () => {
  it('mostra o nome do arquivo e "Enviando..." durante o upload', () => {
    render(
      <UploadRow fileName="tickets.csv" status="uploading" onRetry={vi.fn()} onDismiss={vi.fn()} />,
    )

    expect(screen.getByText('tickets.csv')).toBeInTheDocument()
    expect(screen.getByText('Enviando...')).toBeInTheDocument()
  })

  it('mostra confirmação de sucesso e não mostra botão de retry', () => {
    render(
      <UploadRow fileName="tickets.csv" status="success" onRetry={vi.fn()} onDismiss={vi.fn()} />,
    )

    expect(screen.getByText('Upload concluído!')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /tentar novamente/i })).not.toBeInTheDocument()
  })

  it('mostra a mensagem de erro e chama onRetry ao clicar em Tentar novamente', async () => {
    const onRetry = vi.fn()
    render(
      <UploadRow
        fileName="tickets.csv"
        status="error"
        errorMessage="Arquivo muito grande."
        onRetry={onRetry}
        onDismiss={vi.fn()}
      />,
    )

    expect(screen.getByText('Arquivo muito grande.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /tentar novamente/i }))
    expect(onRetry).toHaveBeenCalledOnce()
  })

  it('usa a mensagem de erro padrão quando errorMessage não é informado', () => {
    render(
      <UploadRow fileName="tickets.csv" status="error" onRetry={vi.fn()} onDismiss={vi.fn()} />,
    )

    expect(screen.getByText('Falha ao enviar o arquivo.')).toBeInTheDocument()
  })

  it('chama onDismiss ao clicar em remover', async () => {
    const onDismiss = vi.fn()
    render(
      <UploadRow fileName="tickets.csv" status="uploading" onRetry={vi.fn()} onDismiss={onDismiss} />,
    )

    await userEvent.click(screen.getByRole('button', { name: /remover arquivo/i }))
    expect(onDismiss).toHaveBeenCalledOnce()
  })
})
