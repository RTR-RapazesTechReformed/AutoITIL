import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import ThemeToggle from '@/components/ThemeToggle'
import { PRIORITY_STYLES } from '@/lib/priority'

// V2 — Direção A "Pastel Flutuante": fundo pontilhado
// + elementos flutuando em ângulos leves. Só usado aqui na landing — as telas operacionais
// (Kanban/Dashboard/Ingestão/Métricas) ficam com o fundo liso, pra não
// competir com a densidade de informação real.
const FEATURES = [
  {
    title: 'Classificação em cascata',
    body: 'Um modelo de IA (BERT) classifica o tipo ITIL e a área responsável, com um modelo substituto entrando em ação quando o principal não está disponível.',
  },
  {
    title: 'Limiar de confiança calibrado',
    body: 'Tickets com confiança abaixo do limite configurado vão direto para revisão humana, em vez de fingir certeza.',
  },
  {
    title: 'Rastreável de ponta a ponta',
    body: 'Cada ticket guarda o arquivo original, a classificação e o histórico de status que o geraram.',
  },
]

function Landing() {
  return (
    <div className="min-h-screen bg-background">
      <div
        className="relative overflow-hidden"
        style={{
          backgroundImage:
            'radial-gradient(circle, color-mix(in srgb, var(--primary) 18%, transparent) 1.5px, transparent 1.5px)',
          backgroundSize: '18px 18px',
        }}
      >
        <header className="mx-auto flex max-w-6xl items-center justify-between px-4 py-5">
          <span className="font-semibold">AutoITIL</span>
          <div className="flex items-center gap-2">
            <ThemeToggle className="size-10 sm:size-8" />
            <Button asChild variant="outline" size="sm" className="h-9 px-3 sm:h-7 sm:px-2.5">
              <Link to="/ingestao">Entrar no app</Link>
            </Button>
          </div>
        </header>

        <div className="mx-auto grid max-w-6xl gap-10 px-4 py-12 md:grid-cols-2 md:items-center md:py-24">
          <div className="relative z-10 max-w-lg">
            <h1 className="text-3xl leading-tight font-bold text-balance md:text-5xl">
              Triagem de tickets de TI, automática e rastreável
            </h1>
            <p className="mt-4 max-w-md text-lg text-muted-foreground">
              Suba uma planilha, deixe o modelo classificar tipo ITIL e área responsável,
              acompanhe tudo no Kanban.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Button asChild size="lg" className="h-11 px-6">
                <Link to="/ingestao">Começar</Link>
              </Button>
              <Button asChild variant="ghost" size="lg" className="h-11 px-6">
                <Link to="/kanban">Ver o Kanban</Link>
              </Button>
            </div>
          </div>

          <div className="relative hidden md:block" aria-hidden="true">
            <div className="absolute top-4 left-8 h-36 w-36 rounded-full bg-[color-mix(in_srgb,var(--chart-7)_45%,transparent)] blur-2xl" />
            <div className="absolute right-4 bottom-0 h-44 w-44 rounded-full bg-[color-mix(in_srgb,var(--primary)_35%,transparent)] blur-2xl" />
            <div className="relative rotate-[-4deg] rounded-2xl border bg-card p-4 shadow-sm">
              <p className="text-xs text-muted-foreground">TCK-0142 · Rede</p>
              <p className="mt-1 text-sm font-medium">VPN não conecta desde ontem</p>
              <span
                className={`mt-2 inline-block rounded-full px-2 py-0.5 text-[11px] font-medium ${PRIORITY_STYLES.P1}`}
              >
                P1
              </span>
            </div>
            <div className="relative mt-4 ml-16 max-w-xs rotate-[3deg] rounded-2xl border bg-card p-4 shadow-sm">
              <p className="text-xs text-muted-foreground">Confiança média (N1)</p>
              <p className="mt-1 text-2xl font-semibold tabular-nums">0.91</p>
            </div>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-6xl px-4 py-10 sm:py-16">
        <div className="grid gap-4 sm:grid-cols-3">
          {FEATURES.map((feature) => (
            <div key={feature.title} className="rounded-2xl border bg-card p-5 shadow-sm">
              <h2 className="font-medium">{feature.title}</h2>
              <p className="mt-2 text-sm text-muted-foreground">{feature.body}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default Landing
