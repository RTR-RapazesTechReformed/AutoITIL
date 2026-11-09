import type { IngestionFunnel } from '@/lib/api'

function formatPercent(value: number | null) {
  if (value === null) return '—'
  return `${(value * 100).toFixed(1)}%`
}

/** Funil do pipeline como barras horizontais proporcionais.
 *
 *  Barras horizontais e não o funil trapezoidal clássico: as etapas aqui
 *  não são subconjuntos umas das outras (uma linha lida vira um ticket, mas
 *  um upload contém muitas linhas), então o estreitamento trapezoidal
 *  sugeriria uma relação de perda que não existe entre todas as etapas.
 *  A barra proporcional comunica magnitude sem inventar essa semântica.
 */
function FunnelPanel({ data }: { data: IngestionFunnel }) {
  const maior = Math.max(...data.etapas.map((e) => e.total), 1)

  return (
    <div className="rounded-lg border bg-card p-4 shadow-sm">
      <div className="space-y-3">
        {data.etapas.map((etapa) => (
          <div key={etapa.etapa}>
            <div className="mb-1 flex items-baseline justify-between text-sm">
              <span>{etapa.etapa}</span>
              <span className="font-mono font-medium tabular-nums">{etapa.total}</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-primary transition-all"
                style={{ width: `${(etapa.total / maior) * 100}%` }}
              />
            </div>
          </div>
        ))}
      </div>

      <div className="mt-4 grid grid-cols-3 gap-2 border-t pt-3 text-xs text-muted-foreground">
        <div>
          <span className="block font-medium text-foreground">
            {formatPercent(data.taxa_revisao)}
          </span>
          revisados
        </div>
        <div>
          <span className="block font-medium text-foreground">
            {formatPercent(data.taxa_enriquecimento)}
          </span>
          enriquecidos
        </div>
        <div>
          <span className="block font-medium text-foreground">{data.uploads_falhos}</span>
          uploads falhos
        </div>
      </div>
    </div>
  )
}

export default FunnelPanel
