import StatTile from '@/components/StatTile'
import TimeSeriesPanel from '@/components/TimeSeriesPanel'
import {
  getClassificationMetricsHistory,
  getEnrichmentFeedbackSummary,
  getEnrichmentMetricsHistory,
  getSystemMetricsHistory,
  getThroughput,
} from '@/lib/api'
import { useApiData } from '@/lib/useApiData'
import StateFeedback from '@/components/StateFeedback'

/** Rótulo do eixo de tempo: dia/mês antes da hora.
 *
 *  Só com a hora, uma série que atravessa dias mostra "23:39" ao lado de
 *  "14:46" sem nada indicando que são datas diferentes — e o eixo, que é
 *  contínuo, coloca um intervalo de 18 horas do lado de um de 3 minutos.
 */
function formatTime(iso: string) {
  const data = new Date(iso)
  const dia = data.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })
  const hora = data.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
  return `${dia} ${hora}`
}

function formatPercent(value: number | null) {
  if (value === null) return '—'
  return `${(value * 100).toFixed(1)}%`
}

function Desempenho() {
  const {
    data: sistemaHistorico,
    loading: sistemaLoading,
    error: sistemaError,
    refetch: refetchSistema,
  } = useApiData(() => getSystemMetricsHistory(), [])
  const {
    data: gemmaHistorico,
    loading: gemmaLoading,
    error: gemmaError,
    refetch: refetchGemma,
  } = useApiData(() => getEnrichmentMetricsHistory(), [])
  const {
    data: classificacaoHistorico,
    loading: classificacaoLoading,
    error: classificacaoError,
    refetch: refetchClassificacao,
  } = useApiData(() => getClassificationMetricsHistory(), [])
  const {
    data: throughput,
    loading: throughputLoading,
    error: throughputError,
    refetch: refetchThroughput,
  } = useApiData(getThroughput, [])
  const {
    data: feedbackSummary,
    loading: feedbackLoading,
    error: feedbackError,
    refetch: refetchFeedback,
  } = useApiData(getEnrichmentFeedbackSummary, [])

  const cpuMedia =
    sistemaHistorico && sistemaHistorico.length > 0
      ? sistemaHistorico.reduce((acc, a) => acc + a.cpu_percent, 0) /
        sistemaHistorico.length
      : null
  const memAtual =
    sistemaHistorico && sistemaHistorico.length > 0
      ? sistemaHistorico[sistemaHistorico.length - 1].memory_rss_mb
      : null

  return (
    <div className="space-y-6">
      {/* Faixa de resumo: os números que a aba existe para comunicar, antes
          dos gráficos que os detalham. Sem isso, a aba era quatro seções de
          gráficos sem hierarquia. */}
      <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
        <StatTile
          label="Custo por chamado"
          value={
            throughput && throughput.ms_por_chamado_total > 0
              ? `${throughput.ms_por_chamado_total.toFixed(0)} ms`
              : '—'
          }
          hint={
            throughput?.chamados_por_minuto_total
              ? `~${throughput.chamados_por_minuto_total.toFixed(0)} chamados/min de CPU`
              : 'sem classificações registradas'
          }
          destaque
        />
        <StatTile
          label="CPU média do processo"
          value={cpuMedia !== null ? `${cpuMedia.toFixed(1)}%` : '—'}
          hint={
            sistemaHistorico ? `média de ${sistemaHistorico.length} amostras` : undefined
          }
        />
        <StatTile
          label="Memória residente"
          value={memAtual !== null ? `${memAtual.toFixed(0)} MB` : '—'}
          hint="última amostra · inclui os modelos carregados em memória (BERT e Gemma 3 somam alguns GB)"
        />
        <StatTile
          label="Feedback positivo"
          value={
            feedbackSummary && feedbackSummary.total_votados > 0
              ? formatPercent(feedbackSummary.percentual_positivo)
              : '—'
          }
          hint={
            feedbackSummary && feedbackSummary.total_votados > 0
              ? `${feedbackSummary.positivos} de ${feedbackSummary.total_votados} votos positivos (${feedbackSummary.total_enriquecidos} enriquecidos no total)`
              : 'sem votos registrados'
          }
        />
      </div>

      <StateFeedback
        loading={feedbackLoading}
        error={feedbackError}
        onRetry={refetchFeedback}
        loadingLabel="Carregando feedback do enriquecimento..."
      />

      <div>
        <h2 className="mb-3 font-medium">Vazão do classificador</h2>
        <StateFeedback
          loading={throughputLoading}
          error={throughputError}
          onRetry={refetchThroughput}
          loadingLabel="Carregando vazão..."
        />
        {!throughputLoading && !throughputError && throughput && (
          throughput.niveis.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Nenhuma classificação registrada ainda.
            </p>
          ) : (
            <div className="overflow-x-auto rounded-lg border bg-card shadow-sm">
              <table className="w-full text-sm">
                <thead className="border-b text-left whitespace-nowrap text-muted-foreground">
                  <tr>
                    <th className="px-4 py-2 font-medium">Nível</th>
                    <th className="px-4 py-2 font-medium">Modelo</th>
                    <th className="px-4 py-2 text-right font-medium">Chamados</th>
                    <th className="px-4 py-2 text-right font-medium">ms / chamado</th>
                    <th className="px-4 py-2 text-right font-medium">Tokens / chamado</th>
                    <th className="px-4 py-2 text-right font-medium">Chamados / min</th>
                  </tr>
                </thead>
                <tbody>
                  {throughput.niveis.map((n) => (
                    <tr key={`${n.nivel}-${n.arquitetura}`} className="border-b last:border-0">
                      <td className="px-4 py-2">Nível {n.nivel}</td>
                      <td className="px-4 py-2 uppercase">{n.arquitetura}</td>
                      <td className="px-4 py-2 text-right tabular-nums">{n.chamados}</td>
                      <td className="px-4 py-2 text-right tabular-nums">
                        {n.ms_por_chamado.toFixed(1)}
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums">
                        {n.tokens_por_chamado.toFixed(1)}
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums">
                        {n.chamados_por_minuto.toFixed(0)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="border-t px-4 py-2 text-xs text-muted-foreground">
                Um chamado atravessa os dois níveis, então o custo total por chamado é a
                soma das linhas: <strong>{throughput.ms_por_chamado_total.toFixed(1)} ms</strong>.
              </p>
            </div>
          )
        )}
      </div>

      <div>
        <h2 className="mb-3 font-medium">Sistema</h2>
        <StateFeedback
          loading={sistemaLoading}
          error={sistemaError}
          onRetry={refetchSistema}
          loadingLabel="Carregando métricas de sistema..."
        />
        {!sistemaLoading && !sistemaError && sistemaHistorico && (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <TimeSeriesPanel
              title="CPU do processo (%)"
              data={sistemaHistorico}
              timeKey="coletado_em"
              lines={[{ dataKey: 'cpu_percent', label: 'CPU %', color: 'var(--chart-1)' }]}
              emptyMessage="Ainda não há amostras de CPU/memória registradas."
              formatX={formatTime}
            />
            <TimeSeriesPanel
              title="Memória usada (MB)"
              data={sistemaHistorico}
              timeKey="coletado_em"
              lines={[{ dataKey: 'memory_rss_mb', label: 'Memória (MB)', color: 'var(--chart-2)' }]}
              emptyMessage="Ainda não há amostras de CPU/memória registradas."
              formatX={formatTime}
            />
          </div>
        )}
      </div>

      <div>
        <h2 className="mb-3 font-medium">Classificação (BERT / SVM)</h2>
        <StateFeedback
          loading={classificacaoLoading}
          error={classificacaoError}
          onRetry={refetchClassificacao}
          loadingLabel="Carregando métricas de classificação..."
        />
        {!classificacaoLoading &&
          !classificacaoError &&
          classificacaoHistorico &&
          classificacaoHistorico.length === 0 && (
            <p className="text-sm text-muted-foreground">
              Ainda não há classificações registradas. Gere tickets a partir de um
              arquivo para popular este gráfico.
            </p>
          )}
        {!classificacaoLoading &&
          !classificacaoError &&
          classificacaoHistorico &&
          classificacaoHistorico.length > 0 && (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <TimeSeriesPanel
                title="Duração por chamado (ms)"
                data={classificacaoHistorico}
                timeKey="criado_em"
                lines={[
                  {
                    dataKey: 'duracao_ms_por_item',
                    label: 'ms / chamado',
                    color: 'var(--chart-1)',
                  },
                ]}
                emptyMessage="Ainda não há classificações registradas."
                formatX={formatTime}
              />
              <TimeSeriesPanel
                title="Tokens de entrada por lote"
                data={classificacaoHistorico}
                timeKey="criado_em"
                lines={[
                  {
                    dataKey: 'tokens_entrada',
                    label: 'Tokens',
                    color: 'var(--chart-2)',
                  },
                ]}
                emptyMessage="Ainda não há classificações registradas."
                formatX={formatTime}
              />
            </div>
          )}
      </div>

      <div>
        <h2 className="mb-3 font-medium">Gemma 3</h2>
        <StateFeedback
          loading={gemmaLoading}
          error={gemmaError}
          onRetry={refetchGemma}
          loadingLabel="Carregando métricas do Gemma 3..."
        />
        {!gemmaLoading && !gemmaError && gemmaHistorico && gemmaHistorico.length === 0 && (
          <p className="text-sm text-muted-foreground">
            Ainda não há chamadas de enriquecimento registradas.
          </p>
        )}
        {!gemmaLoading && !gemmaError && gemmaHistorico && gemmaHistorico.length > 0 && (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <TimeSeriesPanel
              title="Duração por chamada (ms)"
              data={gemmaHistorico}
              timeKey="criado_em"
              lines={[{ dataKey: 'duracao_ms', label: 'Duração (ms)', color: 'var(--chart-3)' }]}
              emptyMessage="Ainda não há chamadas de enriquecimento registradas."
              formatX={formatTime}
            />
            <TimeSeriesPanel
              title="Tokens por chamada"
              data={gemmaHistorico}
              timeKey="criado_em"
              lines={[
                { dataKey: 'tokens_entrada', label: 'Entrada', color: 'var(--chart-4)' },
                { dataKey: 'tokens_saida', label: 'Saída', color: 'var(--chart-5)' },
              ]}
              emptyMessage="Ainda não há chamadas de enriquecimento registradas."
              formatX={formatTime}
            />
          </div>
        )}
      </div>

    </div>
  )
}

export default Desempenho
