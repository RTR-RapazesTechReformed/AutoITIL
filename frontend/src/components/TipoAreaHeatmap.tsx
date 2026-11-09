import { useState } from 'react'
import type { TipoAreaGrade } from '@/lib/api'

type Metrica = 'volume' | 'confianca'

/** Heatmap tipo ITIL (Nível 1) x área responsável (Nível 2).
 *
 *  Os dois gráficos de barra do dashboard mostram as marginais; esta grade
 *  mostra o cruzamento, que é onde a concentração aparece. As bordas
 *  repetem as marginais (totais por linha e por coluna) para que a leitura
 *  completa caiba num painel só.
 *
 *  Duas leituras sobre a mesma grade:
 *    - volume: quantos chamados caíram em cada combinação;
 *    - confiança: quanto o modelo de Nível 2 estava seguro ali, que é o
 *      indicador de onde treinar mais.
 *
 *  O volume usa escala logarítmica porque a distribuição é muito desigual
 *  (uma célula com 181 e outra com 1): numa escala linear tudo que não é a
 *  célula dominante vira branco e a grade não informa nada.
 */
function TipoAreaHeatmap({
  grade,
  limiar,
}: {
  grade: TipoAreaGrade
  limiar?: number | null
}) {
  const [metrica, setMetrica] = useState<Metrica>('volume')
  const [destaque, setDestaque] = useState<{ tipo: string; area: string } | null>(null)
  const { tipos, areas, celulas } = grade

  if (grade.total === 0) {
    return (
      <section className="rounded-lg border bg-card p-4 shadow-sm">
        <h2 className="mb-1 font-medium">Tipo x área</h2>
        <p className="text-sm text-muted-foreground">
          Nenhum chamado classificado nos dois níveis ainda.
        </p>
      </section>
    )
  }

  const celula = (tipo: string, area: string) =>
    celulas.find((c) => c.tipo === tipo && c.area === area)

  const totalPorTipo = (tipo: string) =>
    celulas.filter((c) => c.tipo === tipo).reduce((soma, c) => soma + c.total, 0)
  const totalPorArea = (area: string) =>
    celulas.filter((c) => c.area === area).reduce((soma, c) => soma + c.total, 0)

  const maior = Math.max(...celulas.map((c) => c.total), 1)
  const intensidadeVolume = (total: number) =>
    total === 0 ? 0 : Math.log1p(total) / Math.log1p(maior)

  const colunas = `minmax(120px, 1.2fr) repeat(${areas.length}, minmax(72px, 1fr)) minmax(64px, 0.8fr)`

  return (
    <section className="rounded-lg border bg-card p-5 shadow-sm">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h2 className="font-medium">Tipo x área</h2>
          <p className="text-sm text-muted-foreground">
            Onde a demanda se concentra, cruzando os dois níveis de classificação.
          </p>
        </div>
        <div className="flex gap-1 text-xs" role="group" aria-label="Métrica da grade">
          {(
            [
              ['volume', 'Chamados'],
              ['confianca', 'Confiança média'],
            ] as [Metrica, string][]
          ).map(([valor, rotulo]) => (
            <button
              key={valor}
              type="button"
              onClick={() => setMetrica(valor)}
              aria-pressed={metrica === valor}
              className={`rounded-md border px-3 py-1.5 transition-colors ${
                metrica === valor
                  ? 'border-primary bg-primary/10 font-medium'
                  : 'text-muted-foreground hover:bg-muted'
              }`}
            >
              {rotulo}
            </button>
          ))}
        </div>
      </div>

      <div
        className="grid gap-1 text-sm"
        style={{ gridTemplateColumns: colunas }}
        onMouseLeave={() => setDestaque(null)}
      >
        <div className="px-2 pb-1 text-xs font-medium text-muted-foreground">
          tipo \ área
        </div>
        {areas.map((area) => (
          <div
            key={area}
            className={`truncate px-1 pb-1 text-center text-xs font-medium transition-colors ${
              destaque?.area === area ? 'text-foreground' : 'text-muted-foreground'
            }`}
            title={area}
          >
            {area}
          </div>
        ))}
        <div className="px-1 pb-1 text-center text-xs font-medium text-muted-foreground">
          Total
        </div>

        {tipos.map((tipo) => (
          <div key={tipo} className="contents">
            <div
              className={`flex items-center px-2 text-sm font-medium transition-colors ${
                destaque?.tipo === tipo ? 'text-foreground' : 'text-muted-foreground'
              }`}
            >
              {tipo}
            </div>

            {areas.map((area) => {
              const dados = celula(tipo, area)
              const total = dados?.total ?? 0
              const confianca = dados?.confianca_media ?? null
              const vazia = total === 0

              // Na visão de confiança, a cor é o próprio valor: quanto mais
              // baixo, mais quente. Célula sem chamado não tem confiança
              // nenhuma pra mostrar.
              const intensidade =
                metrica === 'volume'
                  ? intensidadeVolume(total)
                  : confianca === null
                    ? 0
                    : 1 - confianca

              const abaixoDoLimiar =
                metrica === 'confianca' &&
                confianca !== null &&
                limiar != null &&
                confianca < limiar

              const cor = metrica === 'volume' ? 'var(--primary)' : 'var(--destructive)'
              // Acima de ~55% de intensidade o fundo fica escuro demais para
              // o texto padrão; aí o número vira claro.
              const textoClaro = !vazia && intensidade > 0.55
              const naCruz = destaque?.tipo === tipo || destaque?.area === area

              return (
                <div
                  key={area}
                  onMouseEnter={() => setDestaque({ tipo, area })}
                  className={`flex h-12 items-center justify-center rounded-md border text-base tabular-nums transition-all ${
                    vazia
                      ? 'border-dashed border-border/60 text-muted-foreground/40'
                      : 'border-transparent font-medium'
                  } ${textoClaro ? 'text-white' : ''} ${
                    abaixoDoLimiar ? 'ring-2 ring-destructive ring-offset-1 ring-offset-card' : ''
                  } ${naCruz && !vazia ? 'brightness-125' : ''}`}
                  style={
                    vazia
                      ? undefined
                      : {
                          backgroundColor: `color-mix(in oklab, ${cor} ${Math.round(
                            12 + intensidade * 58,
                          )}%, transparent)`,
                        }
                  }
                  title={
                    vazia
                      ? `${tipo} em ${area}: nenhum chamado`
                      : `${tipo} em ${area}: ${total} chamado(s)` +
                        (confianca !== null
                          ? `, confiança média ${confianca.toFixed(3)}`
                          : '')
                  }
                >
                  {vazia
                    ? '·'
                    : metrica === 'volume'
                      ? total
                      : confianca !== null
                        ? confianca.toFixed(2)
                        : '—'}
                </div>
              )
            })}

            <div
              className={`flex h-12 items-center justify-center rounded-md bg-muted/40 text-sm tabular-nums transition-colors ${
                destaque?.tipo === tipo ? 'text-foreground' : 'text-muted-foreground'
              }`}
              title={`${tipo}: ${totalPorTipo(tipo)} chamado(s) no total`}
            >
              {totalPorTipo(tipo)}
            </div>
          </div>
        ))}

        <div className="flex items-center px-2 text-sm font-medium text-muted-foreground">
          Total
        </div>
        {areas.map((area) => (
          <div
            key={area}
            className={`flex h-10 items-center justify-center rounded-md bg-muted/40 text-sm tabular-nums transition-colors ${
              destaque?.area === area ? 'text-foreground' : 'text-muted-foreground'
            }`}
            title={`${area}: ${totalPorArea(area)} chamado(s) no total`}
          >
            {totalPorArea(area)}
          </div>
        ))}
        <div className="flex h-10 items-center justify-center rounded-md bg-muted/60 text-sm font-medium tabular-nums">
          {grade.total}
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span>{metrica === 'volume' ? 'menos chamados' : 'mais confiança'}</span>
          <div className="flex gap-0.5" aria-hidden="true">
            {[0.12, 0.3, 0.45, 0.6, 0.7].map((nivel) => (
              <div
                key={nivel}
                className="h-3 w-6 rounded-sm"
                style={{
                  backgroundColor: `color-mix(in oklab, ${
                    metrica === 'volume' ? 'var(--primary)' : 'var(--destructive)'
                  } ${Math.round(nivel * 100)}%, transparent)`,
                }}
              />
            ))}
          </div>
          <span>{metrica === 'volume' ? 'mais chamados' : 'menos confiança'}</span>
        </div>

        <p className="text-xs text-muted-foreground">
          {metrica === 'volume'
            ? `${grade.total} chamados classificados nos dois níveis${
                grade.sem_area > 0 ? `, ${grade.sem_area} sem área definida` : ''
              }. Escala logarítmica.`
            : `Confiança média do Nível 2. ${
                limiar != null
                  ? `Células destacadas estão abaixo do limiar de ${limiar}, ou seja, vão para revisão humana.`
                  : 'Quanto mais escura, menos segura foi a classificação.'
              }`}
        </p>
      </div>
    </section>
  )
}

export default TipoAreaHeatmap
