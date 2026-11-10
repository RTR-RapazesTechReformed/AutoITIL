// Espelha o limiar_confianca ativo (0.90), recalibrado em F2-1 com probabilidades
// fora do fold (ver docs/f2-1-calibracao-limiar.md). Compartilhado entre TicketCard (Kanban)
// e GeneratedTicketsTable (resumo pós-ingestão).
export const CONFIDENCE_THRESHOLD = 0.9
