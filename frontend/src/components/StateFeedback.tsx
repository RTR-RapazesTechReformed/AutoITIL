import { Loader2 } from 'lucide-react'

type Props = {
  loading?: boolean
  error?: string | null
  onRetry?: () => void
  loadingLabel?: string
}

/** Feedback padrão de loading/erro de rede — usado por todas as páginas que
 * consomem a API (F7-1). Não renderiza nada quando loading=false e error=null.
 *
 * V2 — Direção A "Pastel Flutuante": o estado de
 * loading era uma caixa tracejada estática com texto pequeno cinza —
 * indistinguível de "parado" a olho, e a borda tracejada agora colide
 * visualmente com o Dropzone (que já usa esse mesmo padrão pra "solte
 * aqui"). Virou um card flutuante (mesmo vocabulário do resto da UI) com
 * um spinner de verdade e o rótulo em destaque tipográfico. */
function StateFeedback({ loading, error, onRetry, loadingLabel = 'Carregando...' }: Props) {
  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border bg-card p-10 text-center shadow-sm">
        <Loader2
          className="size-6 text-primary motion-safe:animate-spin"
          strokeWidth={2.5}
          aria-hidden="true"
        />
        <p className="text-base font-medium text-foreground">{loadingLabel}</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center gap-3 rounded-2xl border border-destructive/30 bg-destructive/5 p-8 text-center shadow-sm">
        <p className="text-sm text-destructive">Falha ao carregar os dados.</p>
        {error && <p className="text-xs text-muted-foreground">{error}</p>}
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="rounded-full border px-3.5 py-1.5 text-sm hover:bg-accent"
          >
            Tentar novamente
          </button>
        )}
      </div>
    )
  }

  return null
}

export default StateFeedback
