import { useMemo, useState } from 'react'
import {
  DndContext,
  DragOverlay,
  useDroppable,
  type DragEndEvent,
  type DragStartEvent,
} from '@dnd-kit/core'
import {
  ApiRequestError,
  exportTickets,
  listTickets,
  updateTicketStatus,
  type ExportFormat,
  type EnrichedFields,
  type Ticket,
} from '@/lib/api'
import { downloadBlob } from '@/lib/download'
import { useToast } from '@/lib/toast'
import { STATUS_LABELS } from '@/lib/status'
import { useApiData } from '@/lib/useApiData'
import { useKanbanSensors } from '@/lib/dndSensors'
import { cn } from '@/lib/utils'
import StateFeedback from '@/components/StateFeedback'
import TicketCard, { TicketCardOverlay } from '@/components/TicketCard'

const COLUMN_ORDER = ['triagem', 'a_fazer', 'em_progresso', 'aguardando_revisao_humana', 'concluido']

const COLUMNS = COLUMN_ORDER.map((status) => ({ status, label: STATUS_LABELS[status] ?? status }))

// V2 — Direção A "Pastel Flutuante": cada coluna
// carrega um tint pastel próprio, não só o cabeçalho. Só cores frias (roxo/azul/verde-menta), nunca quentes.

const COLUMN_TINTS: Record<string, string> = {
  triagem: 'bg-[#eef0fd] dark:bg-[#1a1d33]',
  a_fazer: 'bg-[#e6f4f7] dark:bg-[#12262c]',
  em_progresso: 'bg-[#f1e9fb] dark:bg-[#221c38]',
  aguardando_revisao_humana: 'bg-[#ece9fc] dark:bg-[#241c34]', 
  concluido: 'bg-[#e6f7ef] dark:bg-[#112a20]',
}

type ColumnProps = {
  status: string
  label: string
  tickets: Ticket[]
  onEnriched: (ticketId: number, fields: EnrichedFields) => void
  onRevised: (ticketId: number, updated: Ticket) => void
  onFeedback: (ticketId: number, updated: Ticket) => void
}

function Column({ status, label, tickets, onEnriched, onRevised, onFeedback }: ColumnProps) {
  const { setNodeRef, isOver } = useDroppable({ id: status })

  return (
    <div
      ref={setNodeRef}
      // No celular cada raia ocupa ~82% da largura da tela e o board rola
      // de lado com encaixe (uma raia por vez, a próxima aparecendo na
      // borda pra indicar que há mais). De sm pra cima volta ao original:
      // raias fluidas de no mínimo 16rem dividindo o espaço.
      className={
        `flex w-[82vw] shrink-0 snap-center flex-col gap-2 rounded-2xl border border-transparent p-2 sm:w-auto sm:min-w-64 sm:flex-1 ${COLUMN_TINTS[status] ?? 'bg-muted/30'} ` +
        (isOver ? 'ring-2 ring-primary' : '')
      }
    >
      <div className="flex items-center justify-between px-1 pt-1">
        <h2 className="text-sm font-medium">{label}</h2>
        <span className="text-xs text-muted-foreground">{tickets.length}</span>
      </div>
      {/* Bug de scroll/z-index das raias: overflow-y-auto sem overflow-x
          explícito faz o navegador forçar o eixo X pra "auto" também (regra
          do CSS: um eixo overflow != visible força o outro, que era
          visible, a virar auto). Com <DragOverlay> (ver Kanban abaixo) o
          card arrastado não infla mais a caixa desta raia, mas fixamos
          overflow-x-hidden explicitamente como defesa — nenhum conteúdo
          horizontal deveria vazar da raia de qualquer forma. */}
      <div className="flex flex-col gap-2 overflow-x-hidden overflow-y-auto">
        {tickets.map((ticket) => (
          <TicketCard
            key={ticket.id}
            ticket={ticket}
            onEnriched={onEnriched}
            onRevised={onRevised}
            onFeedback={onFeedback}
          />
        ))}
      </div>
    </div>
  )
}

function Kanban() {
  const { showToast } = useToast()
  const sensors = useKanbanSensors()
  const [area, setArea] = useState('')
  const [prioridade, setPrioridade] = useState('')
  const [busca, setBusca] = useState('')
  const [exporting, setExporting] = useState<ExportFormat | null>(null)

  const { data, loading, error, refetch } = useApiData(
    () => listTickets({ page: 1, page_size: 100, area, prioridade, busca }),
    [area, prioridade, busca],
  )

  const [optimisticMoves, setOptimisticMoves] = useState<Record<number, string>>({})
  // Ticket sendo arrastado no momento (ou null fora de um drag) — usado só
  // pra alimentar o card fantasma do <DragOverlay> abaixo.
  const [activeTicket, setActiveTicket] = useState<Ticket | null>(null)
  // F2-4 — cache local do texto enriquecido por ticket, pra refletir na UI
  // assim que a chamada sob demanda termina, sem precisar refazer o fetch
  // da lista inteira (mesmo espírito de optimisticMoves acima).
  const [enrichedOverrides, setEnrichedOverrides] = useState<Record<number, EnrichedFields>>({})
  // Acurácia real — cache local do tipo_itil/area_responsavel revisados
  // por ticket, pra refletir na UI assim que a revisão termina, mesmo
  // espírito de enrichedOverrides acima.
  const [revisaoOverrides, setRevisaoOverrides] = useState<
    Record<number, Pick<Ticket, 'tipo_itil' | 'area_responsavel'>>
  >({})
  // Feedback do enriquecimento — cache local do voto por ticket, mesmo
  // espírito de enrichedOverrides/revisaoOverrides acima.
  const [feedbackOverrides, setFeedbackOverrides] = useState<
    Record<number, Pick<Ticket, 'feedback_enriquecimento'>>
  >({})

  const ticketsByColumn = useMemo(() => {
    const grouped: Record<string, Ticket[]> = {}
    for (const column of COLUMNS) grouped[column.status] = []

    for (const ticket of data?.items ?? []) {
      const status = optimisticMoves[ticket.id] ?? ticket.status
      const descricao_enriquecida = enrichedOverrides[ticket.id] ?? ticket.descricao_enriquecida
      const revisao = revisaoOverrides[ticket.id]
      const feedback = feedbackOverrides[ticket.id]
      grouped[status]?.push({ ...ticket, descricao_enriquecida, ...revisao, ...feedback })
    }
    return grouped
  }, [data, optimisticMoves, enrichedOverrides, revisaoOverrides, feedbackOverrides])

  function handleEnriched(ticketId: number, fields: EnrichedFields) {
    setEnrichedOverrides((prev) => ({ ...prev, [ticketId]: fields }))
  }

  function handleRevised(ticketId: number, updated: Ticket) {
    setRevisaoOverrides((prev) => ({
      ...prev,
      [ticketId]: { tipo_itil: updated.tipo_itil, area_responsavel: updated.area_responsavel },
    }))
  }

  function handleFeedback(ticketId: number, updated: Ticket) {
    setFeedbackOverrides((prev) => ({
      ...prev,
      [ticketId]: { feedback_enriquecimento: updated.feedback_enriquecimento },
    }))
  }

  function handleDragStart(event: DragStartEvent) {
    const ticket = (event.active.data.current as { ticket?: Ticket } | undefined)?.ticket
    setActiveTicket(ticket ?? null)
  }

  function handleDragEnd(event: DragEndEvent) {
    setActiveTicket(null)

    const ticketId = event.active.id as number
    const newStatus = event.over?.id as string | undefined
    if (!newStatus) return

    const ticket = data?.items.find((t) => t.id === ticketId)
    if (!ticket || ticket.status === newStatus) return

    // Atualização otimista — reverte se a chamada falhar.
    setOptimisticMoves((prev) => ({ ...prev, [ticketId]: newStatus }))
    updateTicketStatus(ticketId, newStatus).catch(() => {
      setOptimisticMoves((prev) => {
        const next = { ...prev }
        delete next[ticketId]
        return next
      })
    })
  }

  function handleDragCancel() {
    setActiveTicket(null)
  }

  async function handleExport(format: ExportFormat) {
    setExporting(format)
    try {
      const blob = await exportTickets({ format, area, prioridade, busca })
      downloadBlob(blob, `tickets-classificados.${format}`)
    } catch (err) {
      showToast(err instanceof ApiRequestError ? err.message : 'Falha ao exportar os tickets.', 'error')
    } finally {
      setExporting(null)
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Kanban</h1>
        <p className="text-sm text-muted-foreground">
          <span className="pointer-coarse:hidden">
            Arraste os cards entre as colunas para atualizar o status.
          </span>
          <span className="hidden pointer-coarse:inline">
            Toque e segure um card para arrastá-lo entre as colunas e atualizar o status.
          </span>
        </p>
      </div>

      {/* Filtros: no celular viram uma grade de 2 colunas (busca na linha
          inteira, depois os dois selects, depois as duas exportações) em
          vez de uma pilha de pílulas de larguras diferentes. */}
      <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap">
        <input
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          placeholder="Buscar por código ou título..."
          className="col-span-2 min-w-0 rounded-full border border-border bg-card px-3.5 py-2 text-sm shadow-sm sm:py-1.5"
        />
        <select
          value={area}
          onChange={(e) => setArea(e.target.value)}
          className="min-w-0 rounded-full border border-border bg-card px-3.5 py-2 text-sm shadow-sm sm:py-1.5"
        >
          <option value="">Todas as áreas</option>
          {['Aplicações', 'BD', 'Rede', 'Segurança', 'Servidor'].map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
        <select
          value={prioridade}
          onChange={(e) => setPrioridade(e.target.value)}
          className="min-w-0 rounded-full border border-border bg-card px-3.5 py-2 text-sm shadow-sm sm:py-1.5"
        >
          <option value="">Todas as prioridades</option>
          {['P1', 'P2', 'P3', 'P4'].map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={() => handleExport('csv')}
          disabled={exporting !== null}
          className="rounded-full border border-border bg-card px-3.5 py-2 text-sm shadow-sm disabled:opacity-50 sm:py-1.5"
        >
          {exporting === 'csv' ? 'Exportando...' : 'Exportar CSV'}
        </button>
        <button
          type="button"
          onClick={() => handleExport('xlsx')}
          disabled={exporting !== null}
          className="rounded-full border border-border bg-card px-3.5 py-2 text-sm shadow-sm disabled:opacity-50 sm:py-1.5"
        >
          {exporting === 'xlsx' ? 'Exportando...' : 'Exportar XLSX'}
        </button>
      </div>

      <StateFeedback loading={loading} error={error} onRetry={refetch} loadingLabel="Carregando tickets..." />

      {!loading && !error && data && (
        <DndContext
          sensors={sensors}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
          onDragCancel={handleDragCancel}
        >
          {/* -mx-4/px-4: no celular o board sangra até as bordas da tela
              (o padding do <main> volta por dentro), senão a raia parcial
              à direita seria cortada antes da borda. O encaixe (snap) é
              desligado durante um arraste: a rolagem automática do dnd-kit
              anda em passos pequenos e o encaixe obrigatório puxaria o
              board de volta a cada passo. */}
          <div
            className={cn(
              '-mx-4 flex snap-x snap-mandatory scroll-px-4 gap-3 overflow-x-auto px-4 pb-2 sm:mx-0 sm:snap-none sm:px-0',
              activeTicket && 'snap-none',
            )}
          >
            {COLUMNS.map((column) => (
              <Column
                key={column.status}
                status={column.status}
                label={column.label}
                tickets={ticketsByColumn[column.status] ?? []}
                onEnriched={handleEnriched}
                onRevised={handleRevised}
                onFeedback={handleFeedback}
              />
            ))}
          </div>
          {/* Card fantasma que segue o ponteiro durante o drag — fora do
              contexto de overflow/stacking das raias (dnd-kit posiciona com
              position: fixed + z-index alto), resolvendo o bug de scroll
              indevido e do card "passando por baixo" de outra raia. */}
          <DragOverlay>
            {activeTicket ? <TicketCardOverlay ticket={activeTicket} /> : null}
          </DragOverlay>
        </DndContext>
      )}
    </div>
  )
}

export default Kanban
