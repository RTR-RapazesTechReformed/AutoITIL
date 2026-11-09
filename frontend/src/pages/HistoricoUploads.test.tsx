import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { UploadHistoryEntry } from '@/lib/api'
import HistoricoUploads from './HistoricoUploads'

const { listUploadHistoryMock } = vi.hoisted(() => ({
  listUploadHistoryMock: vi.fn(),
}))

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api')
  return {
    ...actual,
    listUploadHistory: listUploadHistoryMock,
  }
})

beforeEach(() => {
  listUploadHistoryMock.mockReset()
})

function makeEntry(overrides: Partial<UploadHistoryEntry> = {}): UploadHistoryEntry {
  return {
    id: 1,
    nome_original: 'chamados_marco.csv',
    tamanho_bytes: 204800,
    status: 'tickets_gerados',
    total_linhas: 350,
    mensagem_erro: null,
    criado_em: '2026-08-28T14:00:00Z',
    atualizado_em: '2026-08-28T14:02:00Z',
    ...overrides,
  }
}

describe('HistoricoUploads', () => {
  it('mostra o estado de carregamento', () => {
    listUploadHistoryMock.mockReturnValue(new Promise(() => {}))

    render(<HistoricoUploads />)

    expect(screen.getByText('Carregando histórico de uploads...')).toBeInTheDocument()
  })

  it('renderiza a lista de uploads com nome e status', async () => {
    listUploadHistoryMock.mockResolvedValue([makeEntry()])

    render(<HistoricoUploads />)

    await waitFor(() => expect(screen.getByText('chamados_marco.csv')).toBeInTheDocument())
    expect(screen.getByText('Tickets gerados')).toBeInTheDocument()
  })

  it('mostra mensagem quando não há uploads', async () => {
    listUploadHistoryMock.mockResolvedValue([])

    render(<HistoricoUploads />)

    await waitFor(() =>
      expect(screen.getByText('Nenhum upload registrado ainda.')).toBeInTheDocument(),
    )
  })

  it('mostra erro com botão de tentar novamente e recupera ao clicar', async () => {
    listUploadHistoryMock.mockRejectedValueOnce(new Error('falha de rede'))
    listUploadHistoryMock.mockResolvedValueOnce([makeEntry()])

    render(<HistoricoUploads />)

    await waitFor(() => expect(screen.getByText('falha de rede')).toBeInTheDocument())

    await userEvent.click(screen.getByRole('button', { name: 'Tentar novamente' }))

    await waitFor(() => expect(screen.getByText('chamados_marco.csv')).toBeInTheDocument())
  })
})
