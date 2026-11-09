import { useState } from 'react'
import { Loader2, ThumbsDown, ThumbsUp } from 'lucide-react'
import {
  enrichTicket,
  reviseTicketClassification,
  sendEnrichmentFeedback,
  type EnrichedFields,
  type EnrichmentFeedbackValue,
  type RevisaoNivel,
  type Ticket,
} from '@/lib/api'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { PRIORITY_STYLES } from '@/lib/priority'
import { STATUS_LABELS } from '@/lib/status'
import { cn } from '@/lib/utils'

// Valores válidos por nível — mesmo espírito das listas hardcoded já
// usadas nos filtros de Kanban.tsx (refletem as CHECK constraints do
// schema: ck_tipo_itil_nome / ck_area_nome).
const TIPOS_ITIL = ['Incidente', 'Requisição', 'Problema', 'Mudança'] as const
const AREAS = ['Aplicações', 'BD', 'Rede', 'Segurança', 'Servidor'] as const

type Props = {
  ticket: Ticket
  open: boolean
  onOpenChange: (open: boolean) => void
  // F2-4 — mesmo contrato de propagação que TicketCard já usava antes do
  // redesign: o Kanban atualiza o ticket na lista sem refazer o fetch
  // inteiro.
  onEnriched: (ticketId: number, fields: EnrichedFields) => void
  // Acurácia real do classificador — mesmo espírito de onEnriched: o
  // Kanban atualiza o ticket na lista com o valor revisado sem refazer o
  // fetch inteiro.
  onRevised: (ticketId: number, updated: Ticket) => void
  // Feedback do enriquecimento — mesmo espírito de onRevised.
  onFeedback: (ticketId: number, updated: Ticket) => void
}

function EnrichedTextField({ label, value }: { label: string; value: string | null }) {
  return (
    <div>
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <p className="text-sm">{value ?? 'Não informado pelo modelo.'}</p>
    </div>
  )
}

function EnrichedListField({ label, values }: { label: string; values: string[] | null }) {
  return (
    <div>
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      {Array.isArray(values) && values.length > 0 ? (
        <ul className="list-disc space-y-0.5 pl-4 text-sm">
          {values.map((item, index) => (
            <li key={index}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="text-sm">Não informado pelo modelo.</p>
      )}
    </div>
  )
}

type RevisableChipProps = {
  label: string
  value: string
  options: readonly string[]
  disabled: boolean
  onSelect: (value: string) => void
}

// Chip que é, ao mesmo tempo, o gatilho de um Select da nossa biblioteca
// de componentes (radix-ui, mesmo padrão de Dialog em ui/dialog.tsx) —
// clicar nele já abre a lista de opções, sem passo intermediário.
//
// O Select fica DESCONTROLADO de propósito (sem prop `value`): o Radix
// usa o mesmo hook de "estado controlável" por trás de <select> nativo e
// de <Select>, e em ambos, escolher de novo o valor que já estava
// selecionado não dispara onValueChange/onChange — é uma otimização do
// próprio React/Radix, não uma peculiaridade de DOM. Como aqui uma
// "confirmação" (repetir o valor atual) também precisa virar rótulo
// verdadeiro, forçamos o Select a remontar (via `key`) a cada escolha —
// seu estado interno sempre nasce vazio, então qualquer opção clicada,
// mesmo repetindo o valor mostrado no chip, é uma transição real de
// "nada selecionado" pra aquele valor, e o Radix sempre chama
// onValueChange.
function RevisableChip({ label, value, options, disabled, onSelect }: RevisableChipProps) {
  const [resetKey, setResetKey] = useState(0)

  function handleValueChange(novoValor: string) {
    onSelect(novoValor)
    setResetKey((k) => k + 1)
  }

  return (
    <Select key={resetKey} onValueChange={handleValueChange} disabled={disabled}>
      <SelectTrigger
        aria-label={`Revisar ${label}`}
        className="bg-muted hover:bg-[color-mix(in_oklch,var(--muted),var(--foreground)_12%)]"
      >
        {/* placeholder, não children: o Select fica sem `value` controlado
            de propósito (ver comentário acima), então context.value nunca
            deixa de ser undefined dentro desta instância — SelectValue só
            mostra `children` quando há um valor selecionado, então quem
            exibe o valor atual do ticket aqui é sempre o placeholder. */}
        <SelectValue placeholder={value} />
      </SelectTrigger>
      <SelectContent>
        {options.map((option) => (
          <SelectItem key={option} value={option}>
            {option}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

type EnrichmentFeedbackButtonsProps = {
  value: EnrichmentFeedbackValue | null
  disabled: boolean
  onVote: (valor: EnrichmentFeedbackValue) => void
}

// Um voto por ticket, sempre o mais recente — clicar no voto já ativo é
// um no-op (nem chama a API), clicar no oposto troca. Nunca existe botão
// de "desfazer".
function EnrichmentFeedbackButtons({ value, disabled, onVote }: EnrichmentFeedbackButtonsProps) {
  return (
    <div className="flex items-center gap-1">
      <Button
        type="button"
        variant={value === 'up' ? 'default' : 'outline'}
        size="icon-sm"
        aria-label="Marcar enriquecimento como bom"
        aria-pressed={value === 'up'}
        disabled={disabled}
        onClick={() => onVote('up')}
      >
        <ThumbsUp className="size-3.5" />
      </Button>
      <Button
        type="button"
        variant={value === 'down' ? 'destructive' : 'outline'}
        size="icon-sm"
        aria-label="Marcar enriquecimento como ruim"
        aria-pressed={value === 'down'}
        disabled={disabled}
        onClick={() => onVote('down')}
      >
        <ThumbsDown className="size-3.5" />
      </Button>
    </div>
  )
}

function TicketDetailModal({ ticket, open, onOpenChange, onEnriched, onRevised, onFeedback }: Props) {
  const [enriching, setEnriching] = useState(false)
  const [enrichError, setEnrichError] = useState<string | null>(null)
  const [revising, setRevising] = useState(false)
  const [revisaoError, setRevisaoError] = useState<string | null>(null)
  const [sendingFeedback, setSendingFeedback] = useState(false)
  const [feedbackError, setFeedbackError] = useState<string | null>(null)

  function handleEnrich() {
    setEnriching(true)
    setEnrichError(null)
    enrichTicket(ticket.id)
      .then((result) => onEnriched(ticket.id, result.descricao_enriquecida))
      .catch(() => setEnrichError('Falha ao gerar descrição enriquecida.'))
      .finally(() => setEnriching(false))
  }

  function handleRevisar(nivel: RevisaoNivel, valor: string) {
    setRevising(true)
    setRevisaoError(null)
    reviseTicketClassification(ticket.id, nivel, valor)
      .then((updated) => onRevised(ticket.id, updated))
      .catch(() => setRevisaoError('Falha ao registrar revisão.'))
      .finally(() => setRevising(false))
  }

  function handleFeedback(valor: EnrichmentFeedbackValue) {
    if (ticket.feedback_enriquecimento === valor) return
    setSendingFeedback(true)
    setFeedbackError(null)
    sendEnrichmentFeedback(ticket.id, valor)
      .then((updated) => onFeedback(ticket.id, updated))
      .catch(() => setFeedbackError('Falha ao registrar feedback.'))
      .finally(() => setSendingFeedback(false))
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {/* onPointerDown para antes de listeners/attributes do useDraggable do
          TicketCard pai — o Radix DialogPortal move o DOM pra fora do card,
          mas não tira o componente da árvore React, então eventos
          sintéticos de pointer continuam borbulhando pro handler de drag
          (mesmo truque que o ícone de expandir usa em TicketCard.tsx). */}
      <DialogContent onPointerDown={(e) => e.stopPropagation()}>
        <DialogHeader>
          <div className="flex items-center justify-between gap-2 pr-6">
            <DialogTitle>{ticket.codigo}</DialogTitle>
            <span
              className={cn(
                'rounded-full px-2 py-0.5 text-[11px] font-medium',
                PRIORITY_STYLES[ticket.prioridade] ?? 'bg-muted',
              )}
            >
              {ticket.prioridade}
            </span>
          </div>
        </DialogHeader>

        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <p className="text-xs font-medium text-muted-foreground">Tipo</p>
            <RevisableChip
              label="Tipo"
              value={ticket.tipo_itil}
              options={TIPOS_ITIL}
              disabled={revising}
              onSelect={(valor) => handleRevisar('tipo_itil', valor)}
            />
          </div>
          <div>
            <p className="text-xs font-medium text-muted-foreground">Área</p>
            <RevisableChip
              label="Área"
              value={ticket.area_responsavel ?? '—'}
              options={AREAS}
              disabled={revising}
              onSelect={(valor) => handleRevisar('area', valor)}
            />
          </div>
          <div>
            <p className="text-xs font-medium text-muted-foreground">Status</p>
            <span className="rounded-full bg-muted px-2 py-0.5 text-[11px] font-medium">
              {STATUS_LABELS[ticket.status] ?? ticket.status}
            </span>
          </div>
          <div>
            <p className="text-xs font-medium text-muted-foreground">Confiança</p>
            <p>
              {ticket.confianca_n1 !== null ? `${Math.round(ticket.confianca_n1 * 100)}%` : '—'} /{' '}
              {ticket.confianca_n2 !== null ? `${Math.round(ticket.confianca_n2 * 100)}%` : '—'}
            </p>
          </div>
          <div>
            <p className="text-xs font-medium text-muted-foreground">Data de geração</p>
            <p>{new Date(ticket.data_geracao).toLocaleDateString('pt-BR')}</p>
          </div>
          <div>
            <p className="text-xs font-medium text-muted-foreground">Atualizado em</p>
            <p>{new Date(ticket.atualizado_em).toLocaleDateString('pt-BR')}</p>
          </div>
        </div>
        {revisaoError && <p className="text-[11px] text-destructive">{revisaoError}</p>}

        <p className="text-sm leading-snug">{ticket.titulo_sugerido}</p>

        <div className="space-y-3 border-t border-border pt-3">
          <p className="text-sm font-medium">Enriquecimento</p>
          {ticket.descricao_enriquecida ? (
            <div className="space-y-2">
              <EnrichedTextField label="Objetivo" value={ticket.descricao_enriquecida.objetivo} />
              <EnrichedListField
                label="Requisições para completar"
                values={ticket.descricao_enriquecida.requisicoes}
              />
              <EnrichedTextField
                label="Cargo recomendado"
                value={ticket.descricao_enriquecida.cargo_recomendado}
              />
              <div className="flex items-center gap-2 pt-1">
                <p className="text-xs font-medium text-muted-foreground">Essa descrição ajudou?</p>
                <EnrichmentFeedbackButtons
                  value={ticket.feedback_enriquecimento}
                  disabled={sendingFeedback}
                  onVote={handleFeedback}
                />
              </div>
              {feedbackError && <p className="text-[11px] text-destructive">{feedbackError}</p>}
            </div>
          ) : (
            <Button
              type="button"
              variant="outline"
              onClick={handleEnrich}
              disabled={enriching}
              className="w-full gap-2"
            >
              {enriching && (
                <Loader2
                  className="size-4 shrink-0 motion-safe:animate-spin"
                  strokeWidth={2.5}
                  aria-hidden="true"
                />
              )}
              {enriching ? 'Enriquecendo descrição...' : 'Enriquecer descrição'}
            </Button>
          )}
          {enrichError && <p className="text-[11px] text-destructive">{enrichError}</p>}
        </div>
      </DialogContent>
    </Dialog>
  )
}

export default TicketDetailModal
