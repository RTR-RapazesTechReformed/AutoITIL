import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router-dom'
import type {
  EnrichmentFeedbackSummary,
  EnrichmentMetricSample,
  MetricsReport,
  RealAccuracy,
  SystemMetricsSample,
} from '@/lib/api'
import Modelos from './Modelos'

const {
  getMetricsMock,
  getSystemMetricsHistoryMock,
  getEnrichmentMetricsHistoryMock,
  getRealAccuracyMock,
  getEnrichmentFeedbackSummaryMock,
} = vi.hoisted(() => ({
  getMetricsMock: vi.fn(),
  getSystemMetricsHistoryMock: vi.fn(),
  getEnrichmentMetricsHistoryMock: vi.fn(),
  getRealAccuracyMock: vi.fn(),
  getEnrichmentFeedbackSummaryMock: vi.fn(),
}))

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api')
  return {
    ...actual,
    getMetrics: getMetricsMock,
    getSystemMetricsHistory: getSystemMetricsHistoryMock,
    getEnrichmentMetricsHistory: getEnrichmentMetricsHistoryMock,
    getRealAccuracy: getRealAccuracyMock,
    getEnrichmentFeedbackSummary: getEnrichmentFeedbackSummaryMock,
  }
})

beforeEach(() => {
  getMetricsMock.mockReset()
  getSystemMetricsHistoryMock.mockReset()
  getEnrichmentMetricsHistoryMock.mockReset()
  getRealAccuracyMock.mockReset()
  getEnrichmentFeedbackSummaryMock.mockReset()
  getMetricsMock.mockResolvedValue(makeReport())
  getSystemMetricsHistoryMock.mockResolvedValue([makeSystemSample()])
  getEnrichmentMetricsHistoryMock.mockResolvedValue([makeEnrichmentSample()])
  getRealAccuracyMock.mockResolvedValue(makeRealAccuracy())
  getEnrichmentFeedbackSummaryMock.mockResolvedValue(makeFeedbackSummary())
})

function makeReport(overrides: Partial<MetricsReport> = {}): MetricsReport {
  return {
    nivel1: { bert: { model_name: 'bert', macro_f1: 0.9 } },
    nivel2: {},
    ...overrides,
  }
}

function makeSystemSample(overrides: Partial<SystemMetricsSample> = {}): SystemMetricsSample {
  return {
    cpu_percent: 12.4,
    memory_rss_mb: 340.2,
    memory_percent: 3.1,
    uptime_seconds: 5423.7,
    coletado_em: '2026-08-28T14:00:00Z',
    ...overrides,
  }
}

function makeEnrichmentSample(overrides: Partial<EnrichmentMetricSample> = {}): EnrichmentMetricSample {
  return {
    ticket_id: 1,
    duracao_ms: 18000.0,
    tokens_entrada: 120,
    tokens_saida: 60,
    criado_em: '2026-08-28T14:00:00Z',
    ...overrides,
  }
}

function makeRealAccuracy(overrides: Partial<RealAccuracy> = {}): RealAccuracy {
  return {
    nivel1: { macro_f1: null, revisados: 0, total_tickets: 100 },
    nivel2: { macro_f1: null, revisados: 0, total_tickets: 100 },
    ...overrides,
  }
}

function makeFeedbackSummary(
  overrides: Partial<EnrichmentFeedbackSummary> = {},
): EnrichmentFeedbackSummary {
  return {
    total_enriquecidos: 0,
    total_votados: 0,
    positivos: 0,
    negativos: 0,
    percentual_positivo: null,
    ...overrides,
  }
}

function LocationProbe() {
  const location = useLocation()
  return <div data-testid="loc">{location.pathname}{location.search}</div>
}

function renderModelos(initialPath = '/modelos') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Modelos />
      <LocationProbe />
    </MemoryRouter>,
  )
}

describe('Modelos — navegação em abas', () => {
  it('abre em "Qualidade" por padrão, sem param na URL', async () => {
    renderModelos('/modelos')

    await waitFor(() => expect(screen.getByText('BERT')).toBeInTheDocument())
    expect(screen.queryByText('Sistema')).not.toBeInTheDocument()
    expect(getSystemMetricsHistoryMock).not.toHaveBeenCalled()
  })

  it('cai no default "Qualidade" quando ?aba tem valor desconhecido', async () => {
    renderModelos('/modelos?aba=invalido')

    await waitFor(() => expect(screen.getByText('BERT')).toBeInTheDocument())
    expect(screen.queryByText('Sistema')).not.toBeInTheDocument()
  })

  it('abre direto em "Desempenho" quando a URL já traz ?aba=desempenho', async () => {
    renderModelos('/modelos?aba=desempenho')

    await waitFor(() => expect(screen.getByText('Sistema')).toBeInTheDocument())
    expect(screen.getByText('Gemma 3')).toBeInTheDocument()
    expect(screen.queryByText('BERT')).not.toBeInTheDocument()
    expect(getMetricsMock).not.toHaveBeenCalled()
  })

  it('clicar em "Desempenho" busca os dados e mostra as seções, sem refazer fetch de IA', async () => {
    renderModelos('/modelos')
    await waitFor(() => expect(screen.getByText('BERT')).toBeInTheDocument())
    expect(getMetricsMock).toHaveBeenCalledTimes(1)

    await userEvent.click(screen.getByRole('tab', { name: 'Desempenho' }))

    await waitFor(() => expect(screen.getByText('Sistema')).toBeInTheDocument())
    expect(screen.getByText('Gemma 3')).toBeInTheDocument()
    expect(getMetricsMock).toHaveBeenCalledTimes(1)
  })

  it('clicar em uma aba atualiza o param ?aba na URL', async () => {
    renderModelos('/modelos')
    await waitFor(() => expect(screen.getByText('BERT')).toBeInTheDocument())

    await userEvent.click(screen.getByRole('tab', { name: 'Desempenho' }))
    await waitFor(() => expect(screen.getByText('Sistema')).toBeInTheDocument())
    expect(screen.getByTestId('loc')).toHaveTextContent('aba=desempenho')

    await userEvent.click(screen.getByRole('tab', { name: 'Qualidade' }))
    await waitFor(() => expect(screen.getByText('BERT')).toBeInTheDocument())
    expect(screen.getByTestId('loc')).toHaveTextContent('aba=qualidade')
  })
})

describe('Modelos — Sistema e Gemma 3', () => {
  it('renderiza os gráficos quando os dois históricos resolvem com dados', async () => {
    getSystemMetricsHistoryMock.mockResolvedValue([makeSystemSample(), makeSystemSample({ cpu_percent: 20 })])

    renderModelos('/modelos?aba=desempenho')

    await waitFor(() => expect(screen.getByText('Sistema')).toBeInTheDocument())
    expect(screen.getByText('Gemma 3')).toBeInTheDocument()
  })

  it('mostra estado vazio na seção Gemma 3 quando não há chamadas registradas', async () => {
    getEnrichmentMetricsHistoryMock.mockResolvedValue([])

    renderModelos('/modelos?aba=desempenho')

    await waitFor(() =>
      expect(screen.getByText('Ainda não há chamadas de enriquecimento registradas.')).toBeInTheDocument(),
    )
  })

  it('mostra erro isolado na seção Sistema sem afetar a seção Gemma 3', async () => {
    getSystemMetricsHistoryMock.mockRejectedValue(new Error('falha ao coletar métricas de sistema'))

    renderModelos('/modelos?aba=desempenho')

    await waitFor(() => expect(screen.getByText('falha ao coletar métricas de sistema')).toBeInTheDocument())
    expect(screen.getByText('Gemma 3')).toBeInTheDocument()
  })

  it('mostra estado vazio na seção Sistema quando não há amostras registradas', async () => {
    getSystemMetricsHistoryMock.mockResolvedValue([])

    renderModelos('/modelos?aba=desempenho')

    await waitFor(() => {
      const mensagens = screen.getAllByText('Ainda não há amostras de CPU/memória registradas.')
      expect(mensagens.length).toBeGreaterThanOrEqual(1)
    })
  })

  it('mostra erro isolado na seção Gemma 3 sem afetar a seção Sistema', async () => {
    getEnrichmentMetricsHistoryMock.mockRejectedValue(new Error('falha ao coletar métricas do gemma'))

    renderModelos('/modelos?aba=desempenho')

    await waitFor(() => expect(screen.getByText('falha ao coletar métricas do gemma')).toBeInTheDocument())
    expect(screen.getByText('Sistema')).toBeInTheDocument()
  })
})

describe('Modelos — Acurácia real (produção)', () => {
  it('mostra estado vazio quando nenhum nível tem revisões', async () => {
    renderModelos('/modelos')

    await waitFor(() =>
      expect(screen.getByText('Ainda não há tickets revisados.')).toBeInTheDocument(),
    )
  })

  it('mostra o Macro F1 real por nível quando há revisões', async () => {
    getRealAccuracyMock.mockResolvedValue(
      makeRealAccuracy({
        nivel1: { macro_f1: 0.81, revisados: 42, total_tickets: 1585 },
        nivel2: { macro_f1: 0.77, revisados: 38, total_tickets: 1585 },
      }),
    )

    renderModelos('/modelos')

    await waitFor(() => expect(screen.getByTestId('acuracia-real')).toBeInTheDocument())
    const secao = within(screen.getByTestId('acuracia-real'))

    expect(secao.getByText('Nível 1 — Tipo ITIL')).toBeInTheDocument()
    expect(secao.getByText('81.0%')).toBeInTheDocument()
    expect(secao.getByText(/42 chamado\(s\) revisado\(s\), de 1585 classificados/)).toBeInTheDocument()
    expect(secao.getByText('Nível 2 — Área responsável')).toBeInTheDocument()
    expect(secao.getByText('77.0%')).toBeInTheDocument()
    expect(secao.getByText(/38 chamado\(s\) revisado\(s\), de 1585 classificados/)).toBeInTheDocument()
  })

  it('mostra erro isolado na seção de acurácia real sem afetar a seção de F1', async () => {
    getRealAccuracyMock.mockRejectedValue(new Error('falha ao calcular acurácia real'))

    renderModelos('/modelos')

    await waitFor(() => expect(screen.getByText('falha ao calcular acurácia real')).toBeInTheDocument())
    expect(screen.getByText('BERT')).toBeInTheDocument()
  })
})

describe('Modelos — Feedback do enriquecimento', () => {
  it('mostra estado vazio quando não há votos', async () => {
    renderModelos('/modelos?aba=desempenho')

    await waitFor(() =>
      // O feedback virou tile na faixa de resumo do topo (antes repetia o
      // mesmo número que já aparecia na seção logo abaixo).
      expect(screen.getByText('sem votos registrados')).toBeInTheDocument(),
    )
  })

  it('mostra o percentual e as contagens quando há votos', async () => {
    getEnrichmentFeedbackSummaryMock.mockResolvedValue(
      makeFeedbackSummary({
        total_enriquecidos: 320,
        total_votados: 42,
        positivos: 35,
        negativos: 7,
        percentual_positivo: 0.8333333333333334,
      }),
    )

    renderModelos('/modelos?aba=desempenho')

    await waitFor(() => expect(screen.getByText('83.3%')).toBeInTheDocument())
    expect(
      screen.getByText('35 de 42 votos positivos (320 enriquecidos no total)'),
    ).toBeInTheDocument()
  })

  it('mostra erro isolado no feedback sem afetar Sistema/Gemma 3', async () => {
    getEnrichmentFeedbackSummaryMock.mockRejectedValue(new Error('falha ao calcular feedback'))

    renderModelos('/modelos?aba=desempenho')

    await waitFor(() => expect(screen.getByText('falha ao calcular feedback')).toBeInTheDocument())
    expect(screen.getByText('Sistema')).toBeInTheDocument()
  })
})
