import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { getDashboardSummary, getIngestionFunnel, getTipoAreaGrade } from '@/lib/api'
import { useApiData } from '@/lib/useApiData'
import FunnelPanel from '@/components/FunnelPanel'
import StatTile from '@/components/StatTile'
import TipoAreaHeatmap from '@/components/TipoAreaHeatmap'
import StateFeedback from '@/components/StateFeedback'
import TimeSeriesPanel, { SERIES_COLORS } from '@/components/TimeSeriesPanel'

export function formatDate(iso: string) {
  const [, month, day] = iso.split('-')
  return `${day}/${month}`
}

function BarPanel({
  title,
  data,
  dataKey,
  nameKey,
}: {
  title: string
  data: { total: number; [key: string]: string | number }[]
  dataKey: string
  nameKey: string
}) {
  return (
    <section className="rounded-lg border bg-card p-4 shadow-sm">
      <h2 className="mb-3 font-medium">{title}</h2>
      {data.length === 0 ? (
        <p className="text-sm text-muted-foreground">Sem dados ainda.</p>
      ) : (
        <div className="h-64 w-full">
          <ResponsiveContainer>
            <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16 }}>
              <CartesianGrid horizontal={false} stroke="var(--border)" />
              <XAxis type="number" allowDecimals={false} stroke="var(--muted-foreground)" fontSize={12} />
              <YAxis
                type="category"
                dataKey={nameKey}
                width={90}
                stroke="var(--muted-foreground)"
                fontSize={12}
              />
              <Tooltip
                contentStyle={{
                  background: 'var(--popover)',
                  color: 'var(--popover-foreground)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                }}
              />
              <Bar dataKey={dataKey} radius={[0, 4, 4, 0]}>
                {data.map((_, index) => (
                  <Cell key={index} fill={SERIES_COLORS[index % SERIES_COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </section>
  )
}

function Operacao() {
  const { data, loading, error, refetch } = useApiData(getDashboardSummary, [])
  const {
    data: funil,
    loading: funilLoading,
    error: funilError,
    refetch: refetchFunil,
  } = useApiData(getIngestionFunnel, [])
  const {
    data: grade,
    loading: gradeLoading,
    error: gradeError,
    refetch: refetchGrade,
  } = useApiData(getTipoAreaGrade, [])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Operação</h1>
        <p className="text-sm text-muted-foreground">
          Distribuição de tickets por área e prioridade, confiança média dos modelos.
        </p>
      </div>

      <StateFeedback loading={loading} error={error} onRetry={refetch} loadingLabel="Carregando dashboard..." />

      {!loading && !error && data && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatTile
              label="Total de tickets"
              value={String(data.total_tickets)}
              hint={
                funil
                  ? `de ${funil.etapas.find((e) => e.etapa === 'Linhas lidas')?.total ?? 0} linhas lidas`
                  : undefined
              }
              destaque
            />
            <StatTile
              label="Confiança média (Nível 1)"
              value={data.confianca_media.nivel1 !== null ? `${(data.confianca_media.nivel1 * 100).toFixed(1)}%` : '—'}
            />
            <StatTile
              label="Abaixo do limiar"
              value={String(data.abaixo_do_limiar.total)}
              hint={
                data.total_tickets > 0
                  ? `${((data.abaixo_do_limiar.total / data.total_tickets) * 100).toFixed(0)}% dos tickets · limiar ${data.abaixo_do_limiar.limiar_ativo ?? '—'}`
                  : `limiar ${data.abaixo_do_limiar.limiar_ativo ?? '—'}`
              }
            />
            <StatTile
              label="Uso do enriquecimento"
              value={`${data.taxa_enriquecimento.percentual.toFixed(1)}%`}
              hint={`${data.taxa_enriquecimento.enriquecidos} de ${data.taxa_enriquecimento.total} tickets`}
            />
          </div>

          <div>
            <h2 className="mb-1 font-medium">Funil de ingestão</h2>
            <p className="mb-3 text-sm text-muted-foreground">
              Onde o volume some entre o upload e o ticket enriquecido. Cada etapa é
              contada da própria tabela, então a diferença entre elas é a perda real.
            </p>
            <StateFeedback
              loading={funilLoading}
              error={funilError}
              onRetry={refetchFunil}
              loadingLabel="Carregando funil..."
            />
            {!funilLoading && !funilError && funil && <FunnelPanel data={funil} />}
          </div>

          <div>
            <StateFeedback
              loading={gradeLoading}
              error={gradeError}
              onRetry={refetchGrade}
              loadingLabel="Carregando grade tipo x área..."
            />
            {!gradeLoading && !gradeError && grade && (
              <TipoAreaHeatmap grade={grade} limiar={data.abaixo_do_limiar.limiar_ativo} />
            )}
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <BarPanel title="Tickets por área responsável" data={data.por_area} dataKey="total" nameKey="area" />
            <BarPanel
              title="Tickets por prioridade"
              data={data.por_prioridade}
              dataKey="total"
              nameKey="prioridade"
            />
            <BarPanel
              title="Tempo médio por coluna (horas)"
              data={data.tempo_medio_por_coluna.map((row) => ({ ...row, total: row.media_horas }))}
              dataKey="total"
              nameKey="descricao"
            />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <TimeSeriesPanel
              title="Volume por área ao longo do tempo"
              data={data.volume_diario_por_area}
              timeKey="data"
              emptyMessage="Ainda não há tickets suficientes pra montar essa série."
              formatX={formatDate}
            />
            <TimeSeriesPanel
              title="Volume por prioridade ao longo do tempo"
              data={data.volume_diario_por_prioridade}
              timeKey="data"
              emptyMessage="Ainda não há tickets suficientes pra montar essa série."
              formatX={formatDate}
            />
          </div>
        </>
      )}
    </div>
  )
}

export default Operacao
