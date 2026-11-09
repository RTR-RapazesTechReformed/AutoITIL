import { useMemo, useState } from 'react'
import { Search } from 'lucide-react'
import type { GeneratedTicket } from '@/lib/api'
import { PRIORITY_STYLES } from '@/lib/priority'
import { CONFIDENCE_THRESHOLD } from '@/lib/confidence'
import { cn } from '@/lib/utils'

type Props = {
  tickets: GeneratedTicket[]
}

// V2 — Direção A "Pastel Flutuante". Antes disso, o
// resumo pós-ingestão era um <ul> sem estrutura de colunas real — cada
// linha quebrava em lugares diferentes e a prioridade "flutuava" solta.
// Vira uma tabela de verdade (cabeçalho fixo, colunas alinhadas, pill de
// prioridade reaproveitando a mesma paleta do Kanban) com busca client-side
// por código/título — útil de verdade num lote de até 5000 linhas (MAX_ROWS
// do backend), sem inventar paginação nova só pra uma tela de confirmação
// que não é a superfície principal de navegação de tickets (essa é o
// Kanban, com paginação real da API).
function GeneratedTicketsTable({ tickets }: Props) {
  const [busca, setBusca] = useState('')

  const filtrados = useMemo(() => {
    const termo = busca.trim().toLowerCase()
    if (!termo) return tickets
    return tickets.filter(
      (t) => t.id_ticket.toLowerCase().includes(termo) || t.titulo_sugerido.toLowerCase().includes(termo),
    )
  }, [tickets, busca])

  const resumoMensagem =
    tickets.length === 1
      ? '1 ticket gerado e salvo com sucesso.'
      : `${tickets.length} tickets gerados e salvos com sucesso.`

  return (
    <div className="overflow-hidden rounded-2xl border bg-card shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b p-4">
        <p className="text-sm font-medium">{resumoMensagem}</p>
        <div className="relative">
          <Search className="absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
          <input
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="Buscar por código ou título..."
            className="rounded-full border bg-background py-1.5 pr-3 pl-8 text-sm"
          />
        </div>
      </div>

      <div className="max-h-[28rem] overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 z-10 bg-card">
            <tr className="border-b text-left text-xs font-medium tracking-wide text-muted-foreground uppercase">
              <th className="px-4 py-2 font-medium">Código</th>
              <th className="px-4 py-2 font-medium">Título sugerido</th>
              <th className="px-4 py-2 font-medium">Tipo</th>
              <th className="px-4 py-2 font-medium">Área</th>
              <th className="px-4 py-2 text-right font-medium">Confiança</th>
              <th className="px-4 py-2 text-right font-medium">Prioridade</th>
            </tr>
          </thead>
          <tbody>
            {filtrados.map((ticket) => {
              const baixaConfianca = ticket.confianca_n1 < CONFIDENCE_THRESHOLD
              return (
                <tr key={ticket.id_ticket} className="border-b last:border-0 hover:bg-muted/40">
                  <td className="px-4 py-2 font-mono text-xs text-muted-foreground">{ticket.id_ticket}</td>
                  <td className="max-w-xs px-4 py-2 leading-snug">{ticket.titulo_sugerido}</td>
                  <td className="px-4 py-2">
                    <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                      {ticket.tipo_itil}
                    </span>
                  </td>
                  <td className="px-4 py-2">
                    <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                      {ticket.area_responsavel || '—'}
                    </span>
                  </td>
                  <td
                    className={cn(
                      'px-4 py-2 text-right tabular-nums',
                      baixaConfianca ? 'font-medium text-destructive' : 'text-muted-foreground',
                    )}
                  >
                    {(ticket.confianca_n1 * 100).toFixed(0)}%
                  </td>
                  <td className="px-4 py-2 text-right">
                    <span
                      className={cn(
                        'rounded-full px-2 py-0.5 text-[11px] font-medium',
                        PRIORITY_STYLES[ticket.prioridade] ?? 'bg-muted',
                      )}
                    >
                      {ticket.prioridade}
                    </span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>

        {filtrados.length === 0 && (
          <p className="p-6 text-center text-sm text-muted-foreground">
            Nenhum ticket encontrado para &quot;{busca}&quot;.
          </p>
        )}
      </div>
    </div>
  )
}

export default GeneratedTicketsTable
