import { useState } from 'react'
import { useDraggable } from '@dnd-kit/core'
import type { EnrichedFields, Ticket } from '@/lib/api'
import { cn } from '@/lib/utils'
import { PRIORITY_STYLES } from '@/lib/priority'
import { CONFIDENCE_THRESHOLD } from '@/lib/confidence'
import TicketDetailModal from '@/components/TicketDetailModal'

type Props = {
  ticket: Ticket
  // F2-4 — chamado quando o enriquecimento sob demanda termina com sucesso,
  // pra o Kanban atualizar o ticket na lista sem precisar refazer o fetch
  // inteiro (mesmo espírito das atualizações otimistas de status).
  onEnriched?: (ticketId: number, fields: EnrichedFields) => void
  // Acurácia real — chamado quando uma revisão de Tipo ITIL/Área termina
  // com sucesso, mesmo espírito de onEnriched.
  onRevised?: (ticketId: number, updated: Ticket) => void
  // Feedback do enriquecimento — chamado quando um voto 👍/👎 termina com
  // sucesso, mesmo espírito de onRevised.
  onFeedback?: (ticketId: number, updated: Ticket) => void
}

function ExpandIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3" />
    </svg>
  )
}

type TicketCardBodyProps = {
  ticket: Ticket
  baixaConfianca: boolean
  onExpand?: () => void
}

// Conteúdo visual do card, sem os hooks de drag — reaproveitado tanto pelo
// card "real" (arrastável, abaixo) quanto pelo card fantasma renderizado
// dentro do DragOverlay em Kanban.tsx, pra manter os dois com a mesma cara.
function TicketCardBody({ ticket, baixaConfianca, onExpand }: TicketCardBodyProps) {
  return (
    <>
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-xs text-muted-foreground">{ticket.codigo}</span>
        <div className="flex items-center gap-1">
          <span
            className={cn(
              'rounded-full px-2 py-0.5 text-[11px] font-medium',
              PRIORITY_STYLES[ticket.prioridade] ?? 'bg-muted',
            )}
          >
            {ticket.prioridade}
          </span>
          {/* Ícone de expandir — onPointerDown para antes de listeners/
              attributes do useDraggable pra clicar não iniciar um drag do
              card (mesmo truque que o antigo botão de enriquecer usava).
              Sem onExpand (card fantasma do DragOverlay), o ícone só é
              decorativo — sem sentido abrir um modal de um card que nem
              está mais na posição em que foi renderizado. */}
          {onExpand ? (
            <button
              type="button"
              aria-label="Expandir card"
              onPointerDown={(e) => e.stopPropagation()}
              onTouchStart={(e) => e.stopPropagation()}
              onClick={onExpand}
              // before:-inset-3 — o ícone tem 18px, pequeno demais pra dedo.
              // O pseudo-elemento estende a área clicável pra ~42px sem
              // mexer no tamanho visual nem no layout do card.
              className="relative rounded p-0.5 text-muted-foreground before:absolute before:-inset-3 before:content-[''] hover:bg-accent hover:text-foreground"
            >
              <ExpandIcon />
            </button>
          ) : (
            <span aria-hidden="true" className="rounded p-0.5 text-muted-foreground">
              <ExpandIcon />
            </span>
          )}
        </div>
      </div>
      <p className="text-sm leading-snug">
        {ticket.descricao_enriquecida?.objetivo ?? ticket.titulo_sugerido}
      </p>
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{ticket.area_responsavel ?? '—'}</span>
        {baixaConfianca && (
          <span className="rounded-full bg-destructive/10 px-2 py-0.5 font-medium text-destructive">
            baixa confiança
          </span>
        )}
      </div>
    </>
  )
}

function TicketCard({ ticket, onEnriched, onRevised, onFeedback }: Props) {
  // Bug de scroll/z-index das raias (nota no
  // Kanban.tsx): sem <DragOverlay>, aplicar o `transform` de arraste direto
  // neste elemento o mantinha preso ao contexto de overflow/stacking da
  // raia de origem. Agora este elemento só recebe uma opacidade reduzida
  // como placeholder — quem se move visualmente é o card fantasma
  // renderizado pelo <DragOverlay> em Kanban.tsx (fora desse contexto).
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: ticket.id,
    data: { ticket },
  })

  const [detailOpen, setDetailOpen] = useState(false)

  const baixaConfianca = ticket.confianca_n1 !== null && ticket.confianca_n1 < CONFIDENCE_THRESHOLD

  function handleEnriched(ticketId: number, fields: EnrichedFields) {
    onEnriched?.(ticketId, fields)
  }

  function handleRevised(ticketId: number, updated: Ticket) {
    onRevised?.(ticketId, updated)
  }

  function handleFeedback(ticketId: number, updated: Ticket) {
    onFeedback?.(ticketId, updated)
  }

  return (
    <div
      ref={setNodeRef}
      {...listeners}
      {...attributes}
      className={cn(
        // touch-manipulation + select-none no toque: o arraste por toque é
        // "tocar e segurar" (ver lib/dndSensors.ts), o mesmo gesto que o
        // navegador usa pra selecionar texto e abrir o menu de contexto.
        'cursor-grab touch-manipulation space-y-2 rounded-lg border bg-card p-3 text-card-foreground shadow-sm active:cursor-grabbing pointer-coarse:select-none pointer-coarse:[-webkit-touch-callout:none]',
        isDragging && 'opacity-30',
        baixaConfianca && 'border-destructive',
      )}
    >
      <TicketCardBody
        ticket={ticket}
        baixaConfianca={baixaConfianca}
        onExpand={() => setDetailOpen(true)}
      />
      <TicketDetailModal
        ticket={ticket}
        open={detailOpen}
        onOpenChange={setDetailOpen}
        onEnriched={handleEnriched}
        onRevised={handleRevised}
        onFeedback={handleFeedback}
      />
    </div>
  )
}

// Card fantasma renderizado dentro do <DragOverlay> (Kanban.tsx) enquanto
// um ticket está sendo arrastado — puramente visual, sem drag handlers
// nem modal, já que não representa mais uma posição real na lista.
export function TicketCardOverlay({ ticket }: { ticket: Ticket }) {
  const baixaConfianca = ticket.confianca_n1 !== null && ticket.confianca_n1 < CONFIDENCE_THRESHOLD

  return (
    <div className="cursor-grabbing space-y-2 rounded-lg border bg-card p-3 text-card-foreground shadow-lg">
      <TicketCardBody ticket={ticket} baixaConfianca={baixaConfianca} />
    </div>
  )
}

export default TicketCard
