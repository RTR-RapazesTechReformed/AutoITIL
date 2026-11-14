import type { ConfusionMatrix } from '@/lib/api'

/** Heatmap da matriz de confusão das revisões humanas.
 *
 *  Linha = o que o modelo previu, coluna = o que o humano corrigiu. A
 *  diagonal é acerto (o humano confirmou), tudo fora dela é confusão entre
 *  duas classes específicas — que é o dado acionável para retreino.
 *
 *  A intensidade é normalizada pela MAIOR célula fora da diagonal, não pelo
 *  total: a diagonal costuma dominar (o modelo acerta a maioria), e
 *  normalizar por ela deixaria todos os erros visualmente iguais a zero,
 *  escondendo justamente o que interessa.
 */
function ConfusionMatrixPanel({
  matriz,
  titulo,
}: {
  matriz: ConfusionMatrix
  titulo: string
}) {
  const { rotulos, celulas } = matriz

  if (matriz.total_revisado === 0) {
    return (
      <div className="min-w-0 rounded-lg border bg-card p-4 shadow-sm">
        <p className="mb-1 text-sm font-medium">{titulo}</p>
        <p className="text-sm text-muted-foreground">
          Nenhuma revisão registrada ainda. Corrija a classificação de um ticket
          no modal de detalhe para popular esta matriz.
        </p>
      </div>
    )
  }

  const maiorErro = Math.max(
    ...celulas.filter((c) => !c.acerto).map((c) => c.total),
    1,
  )
  const valor = (predito: string, real: string) =>
    celulas.find((c) => c.predito === predito && c.real === real)?.total ?? 0

  return (
    <div className="min-w-0 rounded-lg border bg-card p-4 shadow-sm">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <p className="text-sm font-medium">{titulo}</p>
        <p className="text-xs text-muted-foreground">
          {matriz.acertos}/{matriz.total_revisado} confirmados
        </p>
      </div>

      <div className="overflow-x-auto">
        <table className="text-xs">
          <thead>
            <tr>
              <th className="p-1 text-left font-medium text-muted-foreground">
                previu \ real
              </th>
              {rotulos.map((r) => (
                <th
                  key={r}
                  className="whitespace-nowrap p-1 text-center font-medium text-muted-foreground"
                >
                  {r}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rotulos.map((predito) => (
              <tr key={predito}>
                <th className="whitespace-nowrap p-1 text-left font-medium text-muted-foreground">
                  {predito}
                </th>
                {rotulos.map((real) => {
                  const total = valor(predito, real)
                  const diagonal = predito === real
                  const intensidade = total === 0 ? 0 : total / maiorErro
                  return (
                    <td key={real} className="p-0.5">
                      <div
                        className={`flex h-8 w-12 items-center justify-center rounded tabular-nums ${
                          diagonal
                            ? 'bg-primary/15 font-medium'
                            : total > 0
                              ? 'text-destructive'
                              : 'text-muted-foreground/40'
                        }`}
                        style={
                          diagonal || total === 0
                            ? undefined
                            : {
                                backgroundColor: `color-mix(in oklab, var(--destructive) ${Math.round(
                                  15 + intensidade * 45,
                                )}%, transparent)`,
                              }
                        }
                        title={`Modelo previu "${predito}", humano corrigiu para "${real}": ${total}`}
                      >
                        {total || '·'}
                      </div>
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="mt-3 text-xs text-muted-foreground">
        Diagonal = o humano confirmou a previsão. Fora dela, a célula mostra para
        qual classe a correção foi feita.
      </p>
    </div>
  )
}

export default ConfusionMatrixPanel
