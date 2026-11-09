import { AlertCircle, CheckCircle2 } from 'lucide-react'
import { useToast } from '@/lib/toast'
import { cn } from '@/lib/utils'

/** Pilha de toasts ativos, fixa no canto superior direito — embaixo o toast
 * ficava atrás do rodapé fixo de algumas páginas e saía da primeira "dobra"
 * em telas baixas; em cima ele nunca fica escondido. z-50 casa com o mesmo
 * nível do Dialog (ver components/ui/dialog.tsx) — não compete com um modal
 * aberto, mas fica acima do conteúdo normal da página.
 *
 * flex-col-reverse: toasts.map mantém o mais novo como último item do
 * array (showToast só dá append), e col-reverse desenha o último item no
 * topo da pilha — assim o toast novo sempre entra encostado no canto,
 * empurrando os mais antigos pra baixo, igual antes com bottom-4. */
function ToastViewport() {
  const { toasts } = useToast()

  if (toasts.length === 0) return null

  return (
    <div
      className="fixed top-4 right-4 z-50 flex flex-col-reverse gap-2"
      role="status"
      aria-live="polite"
      aria-atomic="true"
    >
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={cn(
            'flex items-center gap-2 rounded-2xl border bg-card px-4 py-3 text-sm shadow-sm',
            toast.variant === 'error' && 'border-destructive/30 bg-destructive/5 text-destructive',
          )}
        >
          {toast.variant === 'success' ? (
            <CheckCircle2
              className="size-4 shrink-0 text-[#0c7a50] dark:text-[#36a072]"
              strokeWidth={2.5}
              aria-hidden="true"
            />
          ) : (
            <AlertCircle className="size-4 shrink-0" strokeWidth={2.5} aria-hidden="true" />
          )}
          {toast.message}
        </div>
      ))}
    </div>
  )
}

export default ToastViewport
