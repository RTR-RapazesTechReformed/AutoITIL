import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import type { GeneratedTicket, UploadPreview } from '@/lib/api'
import { ToastProvider } from '@/lib/toast'
import ToastViewport from '@/components/ToastViewport'
import Ingestao from './Ingestao'

const { uploadFileMock, generateTicketsFromFileMock } = vi.hoisted(() => ({
  uploadFileMock: vi.fn(),
  generateTicketsFromFileMock: vi.fn(),
}))

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api')
  return {
    ...actual,
    uploadFile: uploadFileMock,
    generateTicketsFromFile: generateTicketsFromFileMock,
  }
})

function makePreview(overrides: Partial<UploadPreview> = {}): UploadPreview {
  return {
    file_id: 'uploads/abc/tickets.csv',
    filename: 'tickets.csv',
    row_count: 10,
    column_count: 3,
    columns: ['desc', 'dt', 'resp'],
    suggested_mapping: {},
    preview_rows: [],
    ...overrides,
  }
}

function makeTicket(overrides: Partial<GeneratedTicket> = {}): GeneratedTicket {
  return {
    id_ticket: 'TCK-001',
    titulo_sugerido: 'Erro ao acessar sistema',
    tipo_itil: 'Incidente',
    area_responsavel: 'Infraestrutura',
    prioridade: 'P1',
    descricao_original: 'Sistema fora do ar',
    data_geracao: '2026-08-27T10:00:00Z',
    id_origem: '1',
    confianca_n1: 0.9,
    confianca_n2: null,
    ...overrides,
  }
}

function renderIngestao() {
  return render(
    <MemoryRouter>
      <ToastProvider>
        <Ingestao />
        <ToastViewport />
      </ToastProvider>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  uploadFileMock.mockReset()
  generateTicketsFromFileMock.mockReset()
})

describe('Ingestao', () => {
  it('mostra os rótulos dos campos de mapeamento acentuados, não a chave interna crua', async () => {
    uploadFileMock.mockResolvedValue(makePreview())

    renderIngestao()

    const file = new File(['a,b,c'], 'tickets.csv', { type: 'text/csv' })
    await userEvent.upload(screen.getByLabelText('Clique para escolher um arquivo'), file)

    await waitFor(() => expect(screen.getByText('Descrição')).toBeInTheDocument())
    expect(screen.getByText('Data')).toBeInTheDocument()
    expect(screen.getByText('Responsável')).toBeInTheDocument()
    expect(screen.queryByText('descricao')).not.toBeInTheDocument()
    expect(screen.queryByText('responsavel')).not.toBeInTheDocument()
  })

  it('usa singular no resumo do preview quando há 1 linha e 1 coluna', async () => {
    uploadFileMock.mockResolvedValue(makePreview({ row_count: 1, column_count: 1 }))

    renderIngestao()

    const file = new File(['a'], 'tickets.csv', { type: 'text/csv' })
    await userEvent.upload(screen.getByLabelText('Clique para escolher um arquivo'), file)

    await waitFor(() => expect(screen.getByText(/1 linha, 1 coluna\./)).toBeInTheDocument())
  })

  it('mostra toast de sucesso no upload e o link "Ir para o Kanban" depois de gerar os tickets', async () => {
    uploadFileMock.mockResolvedValue(
      makePreview({ suggested_mapping: { descricao: 'desc', data: 'dt', responsavel: 'resp' } }),
    )
    generateTicketsFromFileMock.mockResolvedValue([makeTicket()])

    renderIngestao()

    const file = new File(['a,b,c'], 'tickets.csv', { type: 'text/csv' })
    await userEvent.upload(screen.getByLabelText('Clique para escolher um arquivo'), file)

    await waitFor(() =>
      expect(screen.getByText('Arquivo enviado — confira o mapeamento dos campos.')).toBeInTheDocument(),
    )

    await userEvent.click(screen.getByRole('button', { name: 'Confirmar e gerar tickets' }))

    await waitFor(() => expect(screen.getByRole('link', { name: 'Ir para o Kanban' })).toBeInTheDocument())
    expect(screen.getByRole('link', { name: 'Ir para o Kanban' })).toHaveAttribute('href', '/kanban')
  })
})
