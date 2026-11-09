import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

// Ordem fixa de hues categóricos (paleta validada em src/index.css) — nunca
// atribuídos por índice dinâmico/ciclo, sempre na mesma ordem por entidade.
export const SERIES_COLORS = [
  'var(--chart-1)',
  'var(--chart-2)',
  'var(--chart-3)',
  'var(--chart-4)',
  'var(--chart-5)',
  'var(--chart-6)',
  'var(--chart-7)',
  'var(--chart-8)',
]

export type TimeSeriesLine = { dataKey: string; label: string; color: string }

/** Deriva as séries (lines) a partir das próprias chaves de `data`, quando
 * o chamador não sabe de antemão quais séries existem (ex.: nomes de área
 * variam por dado real) — diferente de séries fixas conhecidas (ex.: CPU%,
 * memória), onde o chamador já passa `lines` explicitamente. */
function deriveLines(data: Record<string, string | number | null>[], timeKey: string): TimeSeriesLine[] {
  const keys = new Set<string>()
  for (const row of data) {
    for (const key of Object.keys(row)) {
      if (key !== timeKey) keys.add(key)
    }
  }
  return Array.from(keys)
    .sort()
    .map((key, index) => ({ dataKey: key, label: key, color: SERIES_COLORS[index % SERIES_COLORS.length] }))
}

function TimeSeriesPanel({
  title,
  data,
  lines,
  timeKey,
  emptyMessage,
  formatX = (value: string) => value,
}: {
  title: string
  data: Record<string, string | number | null>[]
  lines?: TimeSeriesLine[]
  timeKey: string
  emptyMessage: string
  formatX?: (value: string) => string
}) {
  const resolvedLines = lines ?? deriveLines(data, timeKey)

  return (
    <section className="rounded-lg border bg-card p-4 shadow-sm">
      <h3 className="mb-3 font-medium">{title}</h3>
      {data.length === 0 ? (
        <p className="text-sm text-muted-foreground">{emptyMessage}</p>
      ) : (
        <div className="h-64 w-full">
          <ResponsiveContainer>
            <LineChart data={data} margin={{ left: 8, right: 16 }}>
              <CartesianGrid stroke="var(--border)" />
              <XAxis
                dataKey={timeKey}
                tickFormatter={(value) => formatX(String(value))}
                stroke="var(--muted-foreground)"
                fontSize={12}
              />
              <YAxis stroke="var(--muted-foreground)" fontSize={12} />
              <Tooltip
                labelFormatter={(value) => formatX(String(value))}
                contentStyle={{
                  background: 'var(--popover)',
                  color: 'var(--popover-foreground)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                }}
              />
              <Legend />
              {resolvedLines.map((line) => (
                <Line
                  key={line.dataKey}
                  type="monotone"
                  dataKey={line.dataKey}
                  name={line.label}
                  stroke={line.color}
                  dot={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </section>
  )
}

export default TimeSeriesPanel
