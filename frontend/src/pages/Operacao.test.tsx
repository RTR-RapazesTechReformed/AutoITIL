import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import type { DashboardSummary } from '@/lib/api'
import Operacao, { formatDate } from './Operacao'

const { getDashboardSummaryMock } = vi.hoisted(() => ({
  getDashboardSummaryMock: vi.fn(),
}))

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api')
  return {
    ...actual,
    getDashboardSummary: getDashboardSummaryMock,
  }
})

beforeEach(() => {
  getDashboardSummaryMock.mockReset()
})

function makeSummary(overrides: Partial<DashboardSummary> = {}): DashboardSummary {
  return {
    total_tickets: 10,
    por_area: [{ area: 'Rede', total: 5 }],
    por_prioridade: [{ prioridade: 'P1', total: 3 }],
    confianca_media: { nivel1: 0.9, nivel2: 0.8 },
    abaixo_do_limiar: { limiar_ativo: 0.9, total: 1 },
    tempo_medio_por_coluna: [{ status: 'triagem', descricao: 'Triagem', media_horas: 2.5 }],
    volume_diario_por_area: [{ data: '2026-08-01', Rede: 2 }],
    volume_diario_por_prioridade: [{ data: '2026-08-01', P1: 2 }],
    taxa_enriquecimento: { enriquecidos: 4, total: 10, percentual: 40 },
    ...overrides,
  }
}

describe('Operação', () => {
  it('renderiza as novas seções operacionais com dado', async () => {
    getDashboardSummaryMock.mockResolvedValue(makeSummary())

    render(<Operacao />)

    await waitFor(() => expect(screen.getByText('Tempo médio por coluna (horas)')).toBeInTheDocument())
    expect(screen.getByText('Volume por área ao longo do tempo')).toBeInTheDocument()
    expect(screen.getByText('Volume por prioridade ao longo do tempo')).toBeInTheDocument()
    // O valor e o denominador agora ficam em elementos separados (StatTile
    // value + hint), para o numero ter destaque visual sobre o contexto.
    expect(screen.getByText('40.0%')).toBeInTheDocument()
    expect(screen.getByText('4 de 10 tickets')).toBeInTheDocument()
  })

  it('mostra estado vazio nas séries de volume quando não há dados', async () => {
    getDashboardSummaryMock.mockResolvedValue(
      makeSummary({ volume_diario_por_area: [], volume_diario_por_prioridade: [] }),
    )

    render(<Operacao />)

    await waitFor(() =>
      expect(screen.getAllByText('Ainda não há tickets suficientes pra montar essa série.').length).toBe(2),
    )
  })

  it('mostra estado vazio no tempo por coluna quando não há transições completas', async () => {
    getDashboardSummaryMock.mockResolvedValue(makeSummary({ tempo_medio_por_coluna: [] }))

    render(<Operacao />)

    await waitFor(() => expect(screen.getByText('Tempo médio por coluna (horas)')).toBeInTheDocument())
    expect(screen.getAllByText('Sem dados ainda.').length).toBeGreaterThanOrEqual(1)
  })

  it('formata data ISO sem sofrer conversão de fuso horário', () => {
    // Regressão: new Date('2026-08-01') é interpretado como UTC meia-noite;
    // em fusos com offset negativo (ex.: America/Sao_Paulo), formatar via
    // toLocaleDateString devolveria o dia anterior (31/07). formatDate deve
    // tratar a string como texto puro, sem passar por Date.
    expect(formatDate('2026-08-01')).toBe('01/08')
    expect(formatDate('2026-01-31')).toBe('31/01')
    expect(formatDate('2026-12-25')).toBe('25/12')
  })
})
