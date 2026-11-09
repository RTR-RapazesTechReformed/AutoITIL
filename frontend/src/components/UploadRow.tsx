import { CheckCircle2, FileSpreadsheet, RotateCw, X } from 'lucide-react'
import { cn } from '@/lib/utils'

type Status = 'uploading' | 'success' | 'error'

// #0c7a50 — verde de sucesso dedicado (5.36:1 em branco), não a hue
// categórica --chart-3 (2.82:1, calibrada pra área de barra grande, não
// texto pequeno). Cor semântica separada do acento de marca, como o skill
// dataviz recomenda: "good/warning/critical" não é a --accent do produto.

type Props = {
  fileName: string
  status: Status
  errorMessage?: string | null
  onRetry: () => void
  onDismiss: () => void
}

// V2 — linha de status por arquivo, mesmo padrão de
// frontend/screens/drag_and_drop_example.jpg (barra de progresso colorida
// por resultado: --primary em andamento, verde sucesso, --destructive
// erro). Sem gradiente de fundo (isso é da Direção B) — card flutuando
// simples, consistente com o resto da Direção A.
function UploadRow({ fileName, status, errorMessage, onRetry, onDismiss }: Props) {
  return (
    <div className="rounded-2xl border bg-card p-4 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2.5">
          <FileSpreadsheet className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          <span className="truncate text-sm font-medium">{fileName}</span>
        </div>
        {status === 'success' ? (
          <CheckCircle2 className="size-4 shrink-0 text-[#0c7a50] dark:text-[#36a072]" aria-hidden="true" />
        ) : (
          <button
            type="button"
            onClick={onDismiss}
            aria-label="Remover arquivo"
            className="shrink-0 text-muted-foreground hover:text-foreground"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        )}
      </div>

      <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className={cn(
            'h-full rounded-full transition-all',
            status === 'uploading' && 'w-2/3 animate-pulse bg-primary',
            status === 'success' && 'w-full bg-[#0c7a50] dark:bg-[#36a072]',
            status === 'error' && 'w-full bg-destructive',
          )}
        />
      </div>

      <div className="mt-1.5 flex items-center justify-between text-xs">
        <span
          className={cn(
            status === 'uploading' && 'text-muted-foreground',
            status === 'success' && 'text-[#0c7a50] dark:text-[#36a072]',
            status === 'error' && 'text-destructive',
          )}
        >
          {status === 'uploading' && 'Enviando...'}
          {status === 'success' && 'Upload concluído!'}
          {status === 'error' && (errorMessage ?? 'Falha ao enviar o arquivo.')}
        </span>
        {status === 'error' && (
          <button
            type="button"
            onClick={onRetry}
            className="flex items-center gap-1 font-medium text-primary hover:underline"
          >
            <RotateCw className="size-3" aria-hidden="true" />
            Tentar novamente
          </button>
        )}
      </div>
    </div>
  )
}

export default UploadRow
