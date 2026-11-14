import { listUploadHistory, type UploadHistoryEntry } from '@/lib/api'
import { useApiData } from '@/lib/useApiData'
import StateFeedback from '@/components/StateFeedback'

const STATUS_LABELS: Record<UploadHistoryEntry['status'], string> = {
  recebido: 'Recebido',
  pre_visualizado: 'Pré-visualizado',
  tickets_gerados: 'Tickets gerados',
  falhou: 'Falhou',
}

const STATUS_BADGE_CLASSES: Record<UploadHistoryEntry['status'], string> = {
  recebido: 'bg-muted text-muted-foreground',
  pre_visualizado: 'bg-blue-100 text-blue-700',
  tickets_gerados: 'bg-green-100 text-green-700',
  falhou: 'bg-destructive/10 text-destructive',
}

function formatBytes(bytes: number) {
  return `${(bytes / 1024).toFixed(1)} KB`
}

function formatDateTime(iso: string) {
  return new Date(iso).toLocaleString('pt-BR')
}

function HistoricoUploads() {
  const { data, loading, error, refetch } = useApiData(listUploadHistory, [])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Histórico de uploads</h1>
        <p className="text-sm text-muted-foreground">
          Todo arquivo enviado, mesmo os que não viraram tickets.
        </p>
      </div>

      <StateFeedback
        loading={loading}
        error={error}
        onRetry={refetch}
        loadingLabel="Carregando histórico de uploads..."
      />

      {!loading && !error && data && data.length === 0 && (
        <div className="rounded-md border border-dashed p-8 text-center text-sm text-muted-foreground">
          Nenhum upload registrado ainda.
        </div>
      )}

      {!loading && !error && data && data.length > 0 && (
        // No celular a mesma tabela é desenhada como lista de cartões (cada
        // <tr> vira uma grade de 2 colunas: nome + status em cima, tamanho e
        // datas embaixo) — 5 colunas lado a lado obrigariam a rolar de lado
        // pra ler uma linha. De sm pra cima volta a ser tabela normal.
        <div className="overflow-x-auto rounded-lg border bg-card shadow-sm">
          <table className="block w-full text-sm sm:table">
            <thead className="hidden sm:table-header-group">
              <tr className="border-b text-left text-muted-foreground">
                <th className="px-4 py-2 font-medium">Arquivo</th>
                <th className="px-4 py-2 font-medium">Tamanho</th>
                <th className="w-px whitespace-nowrap px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium">Enviado em</th>
                <th className="px-4 py-2 font-medium">Atualizado em</th>
              </tr>
            </thead>
            <tbody className="block sm:table-row-group">
              {data.map((entry) => (
                <tr
                  key={entry.id}
                  className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 gap-y-1 border-b px-4 py-3 last:border-0 sm:table-row sm:p-0"
                >
                  <td className="font-medium break-words sm:px-4 sm:py-2 sm:font-normal">
                    {entry.nome_original}
                  </td>
                  <td className="order-last col-span-2 text-xs text-muted-foreground sm:px-4 sm:py-2 sm:text-sm sm:text-foreground">
                    {formatBytes(entry.tamanho_bytes)}
                  </td>
                  <td className="sm:w-px sm:px-4 sm:py-2">
                    <span
                      className={`inline-block whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_BADGE_CLASSES[entry.status]}`}
                      title={entry.mensagem_erro ?? undefined}
                    >
                      {STATUS_LABELS[entry.status]}
                    </span>
                  </td>
                  <td className="col-span-2 text-xs text-muted-foreground sm:px-4 sm:py-2 sm:text-sm sm:text-foreground">
                    <span className="sm:hidden">Enviado em </span>
                    {formatDateTime(entry.criado_em)}
                  </td>
                  <td className="col-span-2 text-xs text-muted-foreground sm:px-4 sm:py-2 sm:text-sm sm:text-foreground">
                    <span className="sm:hidden">Atualizado em </span>
                    {formatDateTime(entry.atualizado_em)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export default HistoricoUploads
