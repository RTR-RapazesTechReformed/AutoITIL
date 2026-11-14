import ConfusionMatrixPanel from '@/components/ConfusionMatrixPanel'
import { getConfusionMatrices, getMetrics, getRealAccuracy } from '@/lib/api'
import { useApiData } from '@/lib/useApiData'
import StateFeedback from '@/components/StateFeedback'

function formatPercent(value: number | undefined) {
  if (value === undefined) return '—'
  return `${(value * 100).toFixed(1)}%`
}

const MODEL_LABELS: Record<string, string> = {
  bert: 'BERT',
  svm_baseline: 'SVM (baseline)',
}

function Qualidade() {
  const { data, loading, error, refetch } = useApiData(getMetrics, [])
  const {
    data: acuraciaReal,
    loading: acuraciaLoading,
    error: acuraciaError,
    refetch: refetchAcuracia,
  } = useApiData(getRealAccuracy, [])

  const {
    data: confusao,
    loading: confusaoLoading,
    error: confusaoError,
    refetch: refetchConfusao,
  } = useApiData(getConfusionMatrices, [])

  const semDados =
    !loading && !error && data && Object.keys(data.nivel1).length === 0 && Object.keys(data.nivel2).length === 0

  const semRevisoes =
    !acuraciaLoading &&
    !acuraciaError &&
    acuraciaReal &&
    acuraciaReal.nivel1.revisados === 0 &&
    acuraciaReal.nivel2.revisados === 0

  return (
    <div className="space-y-6">
      <p className="text-sm text-muted-foreground">
        Comparação de desempenho (Macro F1) entre SVM e BERT, por nível de
        classificação, medida na validação cruzada do conjunto rotulado.
      </p>

      <StateFeedback loading={loading} error={error} onRetry={refetch} loadingLabel="Carregando métricas..." />

      {semDados && (
        <div className="rounded-md border border-dashed p-8 text-center text-sm text-muted-foreground">
          Ainda não há resultados de validação cruzada. Gere o relatório em
          pesquisa_dos_modelos/ pra ver as métricas aqui.
        </div>
      )}

      {!loading && !error && data && !semDados && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {(['nivel1', 'nivel2'] as const).map((nivel) => {
            const modelos = data[nivel]
            if (!modelos || Object.keys(modelos).length === 0) return null

            return (
              <section key={nivel} className="min-w-0 rounded-lg border bg-card p-4 shadow-sm">
                <h2 className="mb-3 font-medium">
                  {nivel === 'nivel1' ? 'Nível 1 — Tipo ITIL' : 'Nível 2 — Área responsável'}
                </h2>
                <div className="space-y-2">
                  {Object.entries(modelos).map(([key, modelo]) => (
                    <div key={key} className="flex items-center justify-between gap-3 rounded-md border px-3 py-2">
                      <span className="text-sm">{MODEL_LABELS[key] ?? key}</span>
                      <span className="font-mono text-sm font-semibold">
                        {formatPercent(modelo.macro_f1)}
                      </span>
                    </div>
                  ))}
                </div>
              </section>
            )
          })}
        </div>
      )}

      <div data-testid="acuracia-real">
        <h2 className="mb-1 font-medium">Correções humanas registradas</h2>
        <p className="mb-3 text-sm text-muted-foreground">
          Macro F1 calculado só sobre os chamados que alguém abriu e revisou.{' '}
          <b>Não é comparável com o número acima</b>: ninguém revisa o que está
          evidentemente certo, então a amostra é enviesada para os casos
          duvidosos e o valor sai bem abaixo do desempenho real.
        </p>
        <StateFeedback
          loading={acuraciaLoading}
          error={acuraciaError}
          onRetry={refetchAcuracia}
          loadingLabel="Carregando acurácia real..."
        />
        {semRevisoes && (
          <p className="text-sm text-muted-foreground">Ainda não há tickets revisados.</p>
        )}
        {!acuraciaLoading && !acuraciaError && acuraciaReal && !semRevisoes && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {(['nivel1', 'nivel2'] as const).map((nivel) => {
              const resultado = acuraciaReal[nivel]
              return (
                <section key={nivel} className="min-w-0 rounded-lg border bg-card p-4 shadow-sm">
                  <h3 className="mb-2 font-medium">
                    {nivel === 'nivel1' ? 'Nível 1 — Tipo ITIL' : 'Nível 2 — Área responsável'}
                  </h3>
                  <p className="font-mono text-lg font-semibold">
                    {resultado.macro_f1 !== null ? formatPercent(resultado.macro_f1) : '—'}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    sobre {resultado.revisados} chamado(s) revisado(s), de{' '}
                    {resultado.total_tickets} classificados
                  </p>
                </section>
              )
            })}
          </div>
        )}
      </div>

      <div data-testid="matriz-confusao">
        <h2 className="mb-1 font-medium">Matriz de confusão (revisões humanas)</h2>
        <p className="mb-3 text-sm text-muted-foreground">
          Onde o modelo erra, não só quanto: cada célula fora da diagonal é uma
          troca entre duas classes específicas — o dado que orienta retreino.
        </p>
        <StateFeedback
          loading={confusaoLoading}
          error={confusaoError}
          onRetry={refetchConfusao}
          loadingLabel="Carregando matriz de confusão..."
        />
        {!confusaoLoading && !confusaoError && confusao && (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <ConfusionMatrixPanel
              matriz={confusao.nivel1}
              titulo="Nível 1 — Tipo ITIL"
            />
            <ConfusionMatrixPanel
              matriz={confusao.nivel2}
              titulo="Nível 2 — Área responsável"
            />
          </div>
        )}
      </div>
    </div>
  )
}

export default Qualidade
