import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { Ticket, TicketsPage } from '@/lib/api'
import { ToastProvider } from '@/lib/toast'
import ToastViewport from '@/components/ToastViewport'
import Kanban from './Kanban'

const { listTicketsMock, updateTicketStatusMock, enrichTicketMock, exportTicketsMock, downloadBlobMock } =
  vi.hoisted(() => ({
    listTicketsMock: vi.fn(),
    updateTicketStatusMock: vi.fn(),
    enrichTicketMock: vi.fn(),
    exportTicketsMock: vi.fn(),
    downloadBlobMock: vi.fn(),
  }))

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api')
  return {
    ...actual,
    listTickets: listTicketsMock,
    updateTicketStatus: updateTicketStatusMock,
    // TicketCard (renderizado dentro de cada coluna) também importa isso —
    // sem o mock aqui, o import de enrichTicket em TicketCard.tsx seria
    // undefined nesses testes.
    enrichTicket: enrichTicketMock,
    exportTickets: exportTicketsMock,
  }
})

vi.mock('@/lib/download', () => ({
  downloadBlob: downloadBlobMock,
}))

function renderKanban() {
  return render(
    <ToastProvider>
      <Kanban />
      <ToastViewport />
    </ToastProvider>,
  )
}

function makeTicket(overrides: Partial<Ticket> = {}): Ticket {
  return {
    id: 1,
    codigo: 'TCK-0001',
    titulo_sugerido: 'VPN caiu',
    descricao_enriquecida: null,
    tipo_itil: 'Incidente',
    area_responsavel: 'Rede',
    prioridade: 'P2',
    status: 'triagem',
    confianca_n1: 0.9,
    confianca_n2: 0.85,
    data_geracao: '2026-08-01T10:00:00Z',
    atualizado_em: '2026-08-01T10:00:00Z',
    feedback_enriquecimento: null,
    ...overrides,
  }
}

function makePage(items: Ticket[]): TicketsPage {
  return { items, meta: { page: 1, page_size: 100, total: items.length, total_pages: 1 } }
}

beforeEach(() => {
  listTicketsMock.mockReset()
  updateTicketStatusMock.mockReset()
  exportTicketsMock.mockReset()
  downloadBlobMock.mockReset()
})

describe('Kanban', () => {
  it('agrupa os tickets nas colunas certas, por status', async () => {
    listTicketsMock.mockResolvedValue(
      makePage([
        makeTicket({ id: 1, codigo: 'TCK-0001', status: 'triagem' }),
        makeTicket({ id: 2, codigo: 'TCK-0002', status: 'concluido' }),
      ]),
    )

    renderKanban()

    await waitFor(() => expect(screen.getByText('TCK-0001')).toBeInTheDocument())
    expect(screen.getByText('TCK-0002')).toBeInTheDocument()

    const triagemColumn = screen.getByText('Triagem').closest('div')!.parentElement!
    const concluidoColumn = screen.getByText('Concluído').closest('div')!.parentElement!
    expect(triagemColumn).toHaveTextContent('TCK-0001')
    expect(concluidoColumn).toHaveTextContent('TCK-0002')
  })

  it('mostra estado de carregamento antes da resposta da API', () => {
    listTicketsMock.mockReturnValue(new Promise(() => {})) // nunca resolve

    renderKanban()

    expect(screen.getByText('Carregando tickets...')).toBeInTheDocument()
  })

  it('mostra erro com botão de retry quando a API falha', async () => {
    listTicketsMock.mockRejectedValueOnce(new Error('falha de rede'))
    listTicketsMock.mockResolvedValueOnce(makePage([]))

    renderKanban()

    await waitFor(() => expect(screen.getByText(/falha de rede/)).toBeInTheDocument())

    await userEvent.click(screen.getByRole('button', { name: 'Tentar novamente' }))

    await waitFor(() => expect(listTicketsMock).toHaveBeenCalledTimes(2))
  })

  it('refiltra por área quando o select de área muda', async () => {
    listTicketsMock.mockResolvedValue(makePage([]))

    renderKanban()
    await waitFor(() => expect(listTicketsMock).toHaveBeenCalledTimes(1))

    await userEvent.selectOptions(screen.getByDisplayValue('Todas as áreas'), 'Rede')

    await waitFor(() =>
      expect(listTicketsMock).toHaveBeenLastCalledWith(
        expect.objectContaining({ area: 'Rede' }),
      ),
    )
  })

  // Regressão: sem overflow-x explícito, o navegador força esse eixo pra
  // "auto" só por causa do overflow-y-auto (regra do CSS: um eixo
  // overflow != visible força o outro, que era visible, a virar auto) —
  // é essa a origem das barras de rolagem X/Y indesejadas nas raias.
  it('a lista de cards da raia define overflow-x explicitamente', async () => {
    listTicketsMock.mockResolvedValue(
      makePage([makeTicket({ id: 1, codigo: 'TCK-0001', status: 'triagem' })]),
    )

    renderKanban()
    await waitFor(() => expect(screen.getByText('TCK-0001')).toBeInTheDocument())

    const cardList = screen.getByText('TCK-0001').closest('[role="button"]')!.parentElement!
    expect(cardList).toHaveClass('overflow-x-hidden', 'overflow-y-auto')
  })

  // Regressão: sem <DragOverlay>, o card arrastado ficava preso no
  // contexto de overflow/stacking da raia de origem (barras de rolagem
  // indevidas, card "por baixo" de outra raia). O card fantasma do
  // DragOverlay some do DOM assim que o drag termina.
  it('mostra um card fantasma via DragOverlay durante o drag, e o remove ao soltar', async () => {
    listTicketsMock.mockResolvedValue(
      makePage([makeTicket({ id: 1, codigo: 'TCK-0001', status: 'triagem' })]),
    )

    renderKanban()
    await waitFor(() => expect(screen.getByText('TCK-0001')).toBeInTheDocument())
    expect(screen.getAllByText('TCK-0001')).toHaveLength(1)

    const card = screen.getByText('TCK-0001').closest('[role="button"]') as HTMLElement
    fireEvent.pointerDown(card, { pointerId: 1, button: 0, isPrimary: true, clientX: 0, clientY: 0 })
    fireEvent.pointerMove(document, { pointerId: 1, clientX: 30, clientY: 30 })

    // Durante o drag: o card original (opacidade reduzida) e o fantasma do
    // DragOverlay coexistem, então o código do ticket aparece duas vezes.
    await waitFor(() => expect(screen.getAllByText('TCK-0001')).toHaveLength(2))

    fireEvent.pointerUp(document, { pointerId: 1 })

    await waitFor(() => expect(screen.getAllByText('TCK-0001')).toHaveLength(1))

    // Causa raiz do flake no teste de export (abaixo): o PointerSensor do
    // dnd-kit, ao ativar um drag, registra um listener de `click` no
    // `document` em fase de captura só pra suprimir o clique fantasma que o
    // navegador dispara depois de um pointerup que terminou um drag. Em
    // `detach()` (chamado em handleEnd), a remoção desse listener é
    // deliberadamente adiada com `setTimeout(..., 50)` — dando tempo pro
    // clique real (gerado pelo browser) ser engolido antes do listener
    // sumir. No jsdom, `fireEvent.pointerUp` não sintetiza um `click`
    // automaticamente, então esse listener capturador some sozinho só
    // depois desses 50ms — e se o próximo teste clicar em algo antes disso,
    // o clique é interceptado (stopPropagation) e nunca chega no handler
    // React. Sem esperar esse timeout aqui, o teste de export abaixo falha
    // de forma dependente de timing (mais forte ainda com fireEvent.click,
    // que não tem nenhum delay embutido entre passos como o userEvent tem).
    await new Promise((resolve) => setTimeout(resolve, 60))
  })

  it('exporta CSV chamando exportTickets com os filtros atuais da tela e dispara o download', async () => {
    listTicketsMock.mockResolvedValue(makePage([]))
    const blob = new Blob(['conteudo'], { type: 'text/csv' })
    exportTicketsMock.mockResolvedValue(blob)

    renderKanban()
    await waitFor(() => expect(listTicketsMock).toHaveBeenCalledTimes(1))

    await userEvent.selectOptions(screen.getByDisplayValue('Todas as áreas'), 'Rede')
    await waitFor(() =>
      expect(listTicketsMock).toHaveBeenLastCalledWith(expect.objectContaining({ area: 'Rede' })),
    )

    fireEvent.click(screen.getByRole('button', { name: 'Exportar CSV' }))

    await waitFor(() =>
      expect(exportTicketsMock).toHaveBeenCalledWith({
        format: 'csv',
        area: 'Rede',
        prioridade: '',
        busca: '',
      }),
    )
    expect(downloadBlobMock).toHaveBeenCalledWith(blob, 'tickets-classificados.csv')
  })

  it('mostra um toast de erro quando o export falha', async () => {
    listTicketsMock.mockResolvedValue(makePage([]))
    exportTicketsMock.mockRejectedValue(new Error('falha de rede'))

    renderKanban()
    await waitFor(() => expect(listTicketsMock).toHaveBeenCalledTimes(1))

    await userEvent.click(screen.getByRole('button', { name: 'Exportar XLSX' }))

    await waitFor(() => expect(screen.getByText('Falha ao exportar os tickets.')).toBeInTheDocument())
    expect(downloadBlobMock).not.toHaveBeenCalled()
  })
})
