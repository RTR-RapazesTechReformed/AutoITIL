// api.ts — cliente HTTP fino pra API do AutoITIL. Sem lib externa (fetch nativo).
// Convenção de envelope: ver docs/api-contract.md na raiz do repo.

export type ApiError = {
  code: string
  message: string
}

export class ApiRequestError extends Error {
  code: string
  status: number

  constructor(status: number, error: ApiError) {
    super(error.message)
    this.code = error.code
    this.status = status
  }
}

import { clearToken, getToken } from './auth'

function applyAuthHeader(headers: Headers): void {
  const token = getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
}

// Uma resposta 401 de qualquer chamada (exceto o próprio login, cuja
// falha de credencial também é 401 mas não significa sessão expirada)
// limpa o token salvo e manda a pessoa pra tela de login.
function handleUnauthorized(status: number, path: string): void {
  if (status === 401 && path !== '/api/auth/login') {
    clearToken()
    window.location.href = '/login'
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  applyAuthHeader(headers)
  const response = await fetch(path, { ...init, headers })
  const contentType = response.headers.get('content-type') ?? ''
  const body = contentType.includes('application/json') ? await response.json() : null

  if (!response.ok) {
    handleUnauthorized(response.status, path)
    const error = body?.error ?? { code: 'UNKNOWN_ERROR', message: response.statusText }
    throw new ApiRequestError(response.status, error)
  }

  return body as T
}

export type ExportFormat = 'csv' | 'xlsx'

// Resultado é um arquivo binário, não JSON — não reaproveita request()/
// requestEnveloped() (que sempre tentam parsear o body como JSON).
export async function exportTickets(params: {
  format: ExportFormat
  area?: string
  prioridade?: string
  busca?: string
}): Promise<Blob> {
  const query = new URLSearchParams()
  query.set('format', params.format)
  if (params.area) query.set('area', params.area)
  if (params.prioridade) query.set('prioridade', params.prioridade)
  if (params.busca) query.set('busca', params.busca)

  const headers = new Headers()
  applyAuthHeader(headers)
  const response = await fetch(`/api/tickets/export?${query}`, { headers })

  if (!response.ok) {
    handleUnauthorized(response.status, '/api/tickets/export')
    const contentType = response.headers.get('content-type') ?? ''
    const body = contentType.includes('application/json') ? await response.json() : null
    const error = body?.error ?? { code: 'UNKNOWN_ERROR', message: 'Falha ao exportar os tickets.' }
    throw new ApiRequestError(response.status, error)
  }

  return response.blob()
}

// Endpoints com envelope {success, data}
async function requestEnveloped<T>(path: string, init?: RequestInit): Promise<T> {
  const body = await request<{ success: boolean; data: T }>(path, init)
  return body.data
}

export type EnrichedFields = {
  objetivo: string
  requisicoes: string[] | null
  cargo_recomendado: string | null
}

export type Ticket = {
  id: number
  codigo: string
  titulo_sugerido: string
  descricao_enriquecida: EnrichedFields | null
  tipo_itil: string
  area_responsavel: string | null
  prioridade: string
  status: string
  confianca_n1: number | null
  confianca_n2: number | null
  data_geracao: string
  atualizado_em: string
  feedback_enriquecimento: 'up' | 'down' | null
}

export type TicketsPage = {
  items: Ticket[]
  meta: { page: number; page_size: number; total: number; total_pages: number }
}

export type TicketFilters = {
  page?: number
  page_size?: number
  area?: string
  prioridade?: string
  status?: string
  busca?: string
}

export function listTickets(filters: TicketFilters = {}): Promise<TicketsPage> {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== '') params.set(key, String(value))
  }
  const query = params.toString()
  return requestEnveloped<TicketsPage>(`/api/tickets${query ? `?${query}` : ''}`)
}

export type TicketStatusUpdate = {
  id: number
  codigo: string
  status: string
  atualizado_em: string
}

export function updateTicketStatus(id: number, status: string): Promise<TicketStatusUpdate> {
  return requestEnveloped<TicketStatusUpdate>(`/api/tickets/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  })
}

export type RevisaoNivel = 'tipo_itil' | 'area'

// Revisão humana de Tipo ITIL/Área — qualquer escolha (inclusive repetir o
// valor já existente) vira rótulo verdadeiro pra acurácia real do
// classificador (ver getRealAccuracy, na seção de Métricas abaixo).
export function reviseTicketClassification(
  id: number,
  nivel: RevisaoNivel,
  valor: string,
): Promise<Ticket> {
  return requestEnveloped<Ticket>(`/api/tickets/${id}/revisao`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ nivel, valor }),
  })
}

// F2-4 — reescreve a descrição do ticket via LLM pequeno, sob demanda.
// Idempotente: repetir a chamada devolve o valor já em cache sem rodar o
// modelo de novo (ver POST /api/tickets/{id}/enrich em docs/api-contract.md).
export type EnrichedDescription = {
  id: number
  descricao_enriquecida: EnrichedFields
}

export function enrichTicket(id: number): Promise<EnrichedDescription> {
  return requestEnveloped<EnrichedDescription>(`/api/tickets/${id}/enrich`, {
    method: 'POST',
  })
}

export type EnrichmentFeedbackValue = 'up' | 'down'

// Feedback humano (👍/👎) sobre a descrição enriquecida — um voto por
// ticket, sempre o mais recente (trocar de valor sobrescreve, sem
// histórico). Ver getEnrichmentFeedbackSummary, na seção de Métricas
// abaixo, pro agregado.
export function sendEnrichmentFeedback(
  id: number,
  valor: EnrichmentFeedbackValue,
): Promise<Ticket> {
  return requestEnveloped<Ticket>(`/api/tickets/${id}/feedback-enriquecimento`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ valor }),
  })
}

export type MetricsReport = {
  generated_at?: string
  source?: string
  nivel1: Record<string, { model_name: string; macro_f1: number; per_class?: Record<string, unknown> }>
  nivel2: Record<string, { model_name: string; macro_f1: number; per_class?: Record<string, unknown> }>
}

export function getMetrics(): Promise<MetricsReport> {
  return request<MetricsReport>('/api/models/quality')
}

export type SystemMetricsSample = {
  cpu_percent: number
  memory_rss_mb: number
  memory_percent: number
  uptime_seconds: number
  coletado_em: string
}

export function getSystemMetricsHistory(limit = 200): Promise<SystemMetricsSample[]> {
  return request<SystemMetricsSample[]>(`/api/models/performance/system-history?limit=${limit}`)
}

export type EnrichmentMetricSample = {
  ticket_id: number | null
  duracao_ms: number
  tokens_entrada: number
  tokens_saida: number
  criado_em: string
}

export function getEnrichmentMetricsHistory(limit = 200): Promise<EnrichmentMetricSample[]> {
  return request<EnrichmentMetricSample[]>(`/api/models/performance/enrichment-history?limit=${limit}`)
}

export type ClassificationMetricSample = {
  nivel: number
  arquitetura: string
  duracao_ms: number
  tokens_entrada: number
  itens: number
  /** duracao_ms / itens — comparável entre lotes de tamanhos diferentes. */
  duracao_ms_por_item: number
  criado_em: string
}

export function getClassificationMetricsHistory(
  limit = 200,
): Promise<ClassificationMetricSample[]> {
  return request<ClassificationMetricSample[]>(
    `/api/models/performance/classification-history?limit=${limit}`,
  )
}

export type FunnelStage = {
  etapa: string
  total: number
  percentual_da_base: number | null
}

export type IngestionFunnel = {
  etapas: FunnelStage[]
  base: number
  uploads_falhos: number
  taxa_revisao: number | null
  taxa_enriquecimento: number | null
}

export function getIngestionFunnel(): Promise<IngestionFunnel> {
  return request<IngestionFunnel>('/api/operations/ingestion-funnel')
}

export type ConfusionCell = {
  predito: string
  real: string
  total: number
  acerto: boolean
}

export type ConfusionMatrix = {
  rotulos: string[]
  celulas: ConfusionCell[]
  total_revisado: number
  acertos: number
  acuracia: number | null
}

export type TipoAreaCelula = {
  tipo: string
  area: string
  total: number
  confianca_media: number | null
}

export type TipoAreaGrade = {
  tipos: string[]
  areas: string[]
  celulas: TipoAreaCelula[]
  total: number
  sem_area: number
}

export function getTipoAreaGrade(): Promise<TipoAreaGrade> {
  return request<TipoAreaGrade>('/api/operations/type-area')
}

export type ConfusionMatrices = {
  nivel1: ConfusionMatrix
  nivel2: ConfusionMatrix
}

export function getConfusionMatrices(): Promise<ConfusionMatrices> {
  return request<ConfusionMatrices>('/api/models/quality/confusion-matrix')
}

export type ThroughputLevel = {
  nivel: number
  arquitetura: string
  chamadas: number
  chamados: number
  ms_por_chamado: number
  tokens_por_chamado: number
  chamados_por_minuto: number
}

export type Throughput = {
  niveis: ThroughputLevel[]
  ms_por_chamado_total: number
  chamados_por_minuto_total: number | null
}

export function getThroughput(): Promise<Throughput> {
  return request<Throughput>('/api/models/performance/throughput')
}

export type RealAccuracyLevel = {
  macro_f1: number | null
  revisados: number
  total_tickets: number
}

export type RealAccuracy = {
  nivel1: RealAccuracyLevel
  nivel2: RealAccuracyLevel
}

export function getRealAccuracy(): Promise<RealAccuracy> {
  return request<RealAccuracy>('/api/models/quality/reviews')
}

export type EnrichmentFeedbackSummary = {
  total_enriquecidos: number
  total_votados: number
  positivos: number
  negativos: number
  percentual_positivo: number | null
}

export function getEnrichmentFeedbackSummary(): Promise<EnrichmentFeedbackSummary> {
  return request<EnrichmentFeedbackSummary>('/api/models/quality/enrichment-feedback')
}

export type DashboardSummary = {
  total_tickets: number
  por_area: { area: string; total: number }[]
  por_prioridade: { prioridade: string; total: number }[]
  confianca_media: { nivel1: number | null; nivel2: number | null }
  abaixo_do_limiar: { limiar_ativo: number | null; total: number }
  tempo_medio_por_coluna: { status: string; descricao: string; media_horas: number }[]
  volume_diario_por_area: Record<string, string | number>[]
  volume_diario_por_prioridade: Record<string, string | number>[]
  taxa_enriquecimento: { enriquecidos: number; total: number; percentual: number }
}

export function getDashboardSummary(): Promise<DashboardSummary> {
  return requestEnveloped<DashboardSummary>('/api/operations/summary')
}

export type UploadPreview = {
  file_id: string
  filename: string
  row_count: number
  column_count: number
  columns: string[]
  suggested_mapping: Record<string, string>
  preview_rows: Record<string, unknown>[]
}

export function uploadFile(file: File): Promise<UploadPreview> {
  const form = new FormData()
  form.append('file', file)
  return requestEnveloped<UploadPreview>('/api/upload', { method: 'POST', body: form })
}

export type GeneratedTicket = {
  id_ticket: string
  titulo_sugerido: string
  tipo_itil: string
  area_responsavel: string
  prioridade: string
  descricao_original: string
  data_geracao: string
  id_origem: string
  confianca_n1: number
  confianca_n2: number | null
}

// Rota autenticada (ver JwtAuthMiddleware) — não reaproveita request()/
// requestEnveloped() porque a resposta de sucesso não segue o envelope
// {success, data} (é a lista de tickets gerados, direto), então o erro
// precisa do mesmo tratamento manual usado em exportTickets().
export async function generateTicketsFromFile(params: {
  filePath: string
  descricao: string
  data?: string
  responsavel?: string
}): Promise<GeneratedTicket[]> {
  const form = new FormData()
  form.append('file_path', params.filePath)
  form.append('descricao', params.descricao)
  form.append('data', params.data ?? '')
  form.append('responsavel', params.responsavel ?? '')
  form.append('format', 'json')

  const headers = new Headers()
  applyAuthHeader(headers)
  const path = '/api/tickets/generate-from-file'
  const response = await fetch(path, { method: 'POST', body: form, headers })

  // Rota roda a cascata BERT em até 5000 linhas (proxy_read_timeout de
  // 300s em nginx.conf/vite.config.ts) — um timeout de proxy real devolve
  // HTML (502/504), não JSON. Igual a request()/exportTickets(): só
  // parseia como JSON se o content-type confirmar, senão response.json()
  // explode com SyntaxError antes de conseguir montar o ApiRequestError.
  const contentType = response.headers.get('content-type') ?? ''
  const body = contentType.includes('application/json') ? await response.json() : null

  if (!response.ok) {
    handleUnauthorized(response.status, path)
    const error = body?.error ?? { code: 'UNKNOWN_ERROR', message: 'Falha ao gerar os tickets.' }
    throw new ApiRequestError(response.status, error)
  }

  return body as GeneratedTicket[]
}

export type UploadHistoryEntry = {
  id: number
  nome_original: string
  tamanho_bytes: number
  status: 'recebido' | 'pre_visualizado' | 'tickets_gerados' | 'falhou'
  total_linhas: number | null
  mensagem_erro: string | null
  criado_em: string
  atualizado_em: string
}

export function listUploadHistory(): Promise<UploadHistoryEntry[]> {
  return requestEnveloped<UploadHistoryEntry[]>('/api/uploads')
}

export type CurrentUser = {
  id: number
  email: string
  is_admin: boolean
  organizacao_id: number
}

export type LoginResponse = {
  access_token: string
  usuario: CurrentUser
}

export function login(email: string, senha: string): Promise<LoginResponse> {
  return requestEnveloped<LoginResponse>('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, senha }),
  })
}

export function getCurrentUser(): Promise<CurrentUser> {
  return request<CurrentUser>('/api/auth/me')
}

export type AdminUser = {
  id: number
  email: string
  is_admin: boolean
  ativo: boolean
}

export function listUsers(): Promise<AdminUser[]> {
  return request<AdminUser[]>('/api/admin/usuarios')
}

export function createUser(payload: {
  email: string
  senha: string
  is_admin: boolean
}): Promise<AdminUser> {
  return requestEnveloped<AdminUser>('/api/admin/usuarios', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function updateUser(
  id: number,
  payload: { ativo?: boolean; is_admin?: boolean },
): Promise<AdminUser> {
  return requestEnveloped<AdminUser>(`/api/admin/usuarios/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export type RelatorioCustoItemResumo = {
  tipo_evento: string
  quantidade_total: number
  custo_total_centavos: number
}

export type RelatorioCustoResumo = {
  id: number
  periodo_inicio: string
  periodo_fim: string
  status: string
  total_centavos: number
}

export type RelatorioCustoDetalhe = RelatorioCustoResumo & {
  organizacao_id: number
  criado_em: string
  fechado_em: string | null
  itens: RelatorioCustoItemResumo[]
}

export type PreviewCusto = {
  itens: RelatorioCustoItemResumo[]
  total_centavos: number
}

export function listarRelatoriosCusto(): Promise<RelatorioCustoResumo[]> {
  return requestEnveloped<RelatorioCustoResumo[]>('/api/custos')
}

export function previewCusto(): Promise<PreviewCusto> {
  return requestEnveloped<PreviewCusto>('/api/custos/preview')
}

export function detalharRelatorioCusto(id: number): Promise<RelatorioCustoDetalhe> {
  return requestEnveloped<RelatorioCustoDetalhe>(`/api/custos/${id}`)
}

export function fecharPeriodoCusto(periodoInicio: string, periodoFim: string): Promise<RelatorioCustoDetalhe> {
  return requestEnveloped<RelatorioCustoDetalhe>('/api/admin/custos/fechar', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ periodo_inicio: periodoInicio, periodo_fim: periodoFim }),
  })
}
