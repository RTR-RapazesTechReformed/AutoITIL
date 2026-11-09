import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ToastProvider } from '@/lib/toast'
import Custos from './Custos'

function renderCustos() {
  return render(
    <ToastProvider>
      <Custos />
    </ToastProvider>,
  )
}

const {
  listarRelatoriosCustoMock,
  previewCustoMock,
  fecharPeriodoCustoMock,
  useCurrentUserMock,
} = vi.hoisted(() => ({
  listarRelatoriosCustoMock: vi.fn(),
  previewCustoMock: vi.fn(),
  fecharPeriodoCustoMock: vi.fn(),
  useCurrentUserMock: vi.fn(),
}))

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api')
  return {
    ...actual,
    listarRelatoriosCusto: listarRelatoriosCustoMock,
    previewCusto: previewCustoMock,
    fecharPeriodoCusto: fecharPeriodoCustoMock,
  }
})

vi.mock('@/components/RequireAuth', async () => {
  const actual = await vi.importActual<typeof import('@/components/RequireAuth')>(
    '@/components/RequireAuth',
  )
  return { ...actual, useCurrentUser: useCurrentUserMock }
})

beforeEach(() => {
  listarRelatoriosCustoMock.mockReset()
  previewCustoMock.mockReset()
  fecharPeriodoCustoMock.mockReset()
  useCurrentUserMock.mockReturnValue({ id: 1, email: 'admin@a.com', is_admin: true, organizacao_id: 1 })
  previewCustoMock.mockResolvedValue({ itens: [], total_centavos: 0 })
  listarRelatoriosCustoMock.mockResolvedValue([])
})

describe('Custos', () => {
  it('mostra o resumo do periodo aberto', async () => {
    previewCustoMock.mockResolvedValue({
      itens: [{ tipo_evento: 'ingestao_linha', quantidade_total: 10, custo_total_centavos: 40 }],
      total_centavos: 100,
    })

    renderCustos()

    await waitFor(() => expect(screen.getByText('R$ 1,00')).toBeInTheDocument())
  })

  it('lista relatorios de custo fechados', async () => {
    listarRelatoriosCustoMock.mockResolvedValue([
      { id: 1, periodo_inicio: '2026-01-01', periodo_fim: '2026-02-01', status: 'fechada', total_centavos: 500 },
    ])

    renderCustos()

    await waitFor(() => expect(screen.getByText('R$ 5,00')).toBeInTheDocument())
  })

  it('botao de fechar periodo so aparece para admin', () => {
    useCurrentUserMock.mockReturnValue({ id: 2, email: 'analista@a.com', is_admin: false, organizacao_id: 1 })

    renderCustos()

    expect(screen.queryByRole('button', { name: /fechar per[ií]odo/i })).not.toBeInTheDocument()
  })

  it('fechar periodo chama fecharPeriodoCusto e recarrega a lista', async () => {
    fecharPeriodoCustoMock.mockResolvedValue({
      id: 2,
      periodo_inicio: '2026-02-01',
      periodo_fim: '2026-03-01',
      status: 'fechada',
      total_centavos: 0,
      organizacao_id: 1,
      criado_em: '2026-02-01T00:00:00Z',
      fechado_em: '2026-02-01T00:00:00Z',
      itens: [],
    })
    const user = userEvent.setup()

    renderCustos()
    await waitFor(() => expect(listarRelatoriosCustoMock).toHaveBeenCalledTimes(1))

    await user.click(screen.getByRole('button', { name: /fechar per[ií]odo/i }))

    await waitFor(() => expect(fecharPeriodoCustoMock).toHaveBeenCalled())
    expect(listarRelatoriosCustoMock).toHaveBeenCalledTimes(2)
  })
})
