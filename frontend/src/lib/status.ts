// Rótulos de exibição por status de ticket — fonte única, reaproveitada
// por Kanban.tsx (rótulo das raias) e TicketDetailModal.tsx (campo Status
// do card expandido). Evita status cru (snake_case) vazando pro usuário.
export const STATUS_LABELS: Record<string, string> = {
  triagem: 'Triagem',
  a_fazer: 'A Fazer',
  em_progresso: 'Em Progresso',
  aguardando_revisao_humana: 'Aguardando Revisão Humana',
  concluido: 'Concluído',
}
