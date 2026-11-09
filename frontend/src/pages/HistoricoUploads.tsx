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
        <div className="overflow-x-auto rounded-lg border bg-card shadow-sm">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-muted-foreground">
                <th className="px-4 py-2 font-medium">Arquivo</th>
                <th className="px-4 py-2 font-medium">Tamanho</th>
                <th className="w-px whitespace-nowrap px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium">Enviado em</th>
                <th className="px-4 py-2 font-medium">Atualizado em</th>
              </tr>
            </thead>
            <tbody>
              {data.map((entry) => (
                <tr key={entry.id} className="border-b last:border-0">
                  <td className="px-4 py-2">{entry.nome_original}</td>
                  <td className="px-4 py-2">{formatBytes(entry.tamanho_bytes)}</td>
                  <td className="w-px px-4 py-2">
                    <span
                      className={`inline-block whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_BADGE_CLASSES[entry.status]}`}
                      title={entry.mensagem_erro ?? undefined}
                    >
                      {STATUS_LABELS[entry.status]}
                    </span>
                  </td>
                  <td className="px-4 py-2">{formatDateTime(entry.criado_em)}</td>
                  <td className="px-4 py-2">{formatDateTime(entry.atualizado_em)}</td>
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
