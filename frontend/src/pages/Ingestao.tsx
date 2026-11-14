import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ApiRequestError,
  generateTicketsFromFile,
  uploadFile,
  type GeneratedTicket,
  type UploadPreview,
} from '@/lib/api'
import StateFeedback from '@/components/StateFeedback'
import Dropzone from '@/components/Dropzone'
import UploadRow from '@/components/UploadRow'
import GeneratedTicketsTable from '@/components/GeneratedTicketsTable'
import { useToast } from '@/lib/toast'

type Step = 'upload' | 'mapping' | 'done'

const CAMPO_LABELS: Record<string, string> = {
  descricao: 'Descrição',
  data: 'Data',
  responsavel: 'Responsável',
}

function pluralizar(n: number, singular: string, plural: string) {
  return n === 1 ? `1 ${singular}` : `${n} ${plural}`
}

function Ingestao() {
  const { showToast } = useToast()
  const [step, setStep] = useState<Step>('upload')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<UploadPreview | null>(null)
  const [mapping, setMapping] = useState({ descricao: '', data: '', responsavel: '' })
  const [tickets, setTickets] = useState<GeneratedTicket[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function processFile(file: File) {
    setSelectedFile(file)
    setLoading(true)
    setError(null)
    try {
      const result = await uploadFile(file)
      setPreview(result)
      setMapping({
        descricao: result.suggested_mapping.descricao ?? '',
        data: result.suggested_mapping.data ?? '',
        responsavel: result.suggested_mapping.responsavel ?? '',
      })
      setStep('mapping')
      showToast('Arquivo enviado — confira o mapeamento dos campos.', 'success')
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : 'Falha ao enviar o arquivo.')
    } finally {
      setLoading(false)
    }
  }

  async function handleGenerate() {
    if (!preview || !mapping.descricao) return

    setLoading(true)
    setError(null)
    try {
      const result = await generateTicketsFromFile({
        filePath: preview.file_id,
        descricao: mapping.descricao,
        data: mapping.data,
        responsavel: mapping.responsavel,
      })
      setTickets(result)
      setStep('done')
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : 'Falha ao gerar os tickets.')
    } finally {
      setLoading(false)
    }
  }

  function reset() {
    setStep('upload')
    setSelectedFile(null)
    setPreview(null)
    setTickets(null)
    setError(null)
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Ingestão de tickets</h1>
        <p className="text-sm text-muted-foreground">
          Envie uma planilha (.csv ou .xlsx) para classificar automaticamente e gerar tickets.
        </p>
      </div>

      {/* Upload e mapeamento ficam num miolo mais estreito (formulário
          curto); o resumo pós-ingestão (abaixo) usa a largura toda —
          é uma tabela, não um formulário. */}
      <div className="max-w-2xl space-y-6">
        {step === 'upload' &&
          (selectedFile ? (
            <UploadRow
              fileName={selectedFile.name}
              status={loading ? 'uploading' : error ? 'error' : 'success'}
              errorMessage={error}
              onRetry={() => processFile(selectedFile)}
              onDismiss={() => {
                setSelectedFile(null)
                setError(null)
              }}
            />
          ) : (
            <Dropzone accept=".csv,.xlsx" hint="Máx. 10MB, 5000 linhas." onFileSelected={processFile} />
          ))}

        {step === 'mapping' && preview && !loading && (
          <div className="space-y-4 rounded-lg border bg-card p-4 shadow-sm">
            {/* wrap-anywhere: nome de arquivo não tem espaço pra quebrar e
                empurrava o card pra fora da tela no celular. */}
            <p className="text-sm wrap-anywhere">
              <strong>{preview.filename}</strong> — {pluralizar(preview.row_count, 'linha', 'linhas')},{' '}
              {pluralizar(preview.column_count, 'coluna', 'colunas')}.
            </p>

            <div className="grid gap-3">
              {(['descricao', 'data', 'responsavel'] as const).map((campo) => (
                <label
                  key={campo}
                  className="flex flex-col gap-1 text-sm sm:flex-row sm:items-center sm:justify-between sm:gap-3"
                >
                  <span>
                    {CAMPO_LABELS[campo]}
                    {campo === 'descricao' && <span className="text-destructive"> *</span>}
                  </span>
                  <select
                    value={mapping[campo]}
                    onChange={(e) => setMapping((prev) => ({ ...prev, [campo]: e.target.value }))}
                    // w-full/min-w-0: o <select> assume a largura da maior opção
                    // (nome de coluna da planilha) e estourava o card no celular.
                    className="w-full min-w-0 rounded-md border bg-background px-2 py-2 sm:w-auto sm:max-w-xs sm:py-1"
                  >
                    <option value="">— não mapear —</option>
                    {preview.columns.map((col) => (
                      <option key={col} value={col}>
                        {col}
                      </option>
                    ))}
                  </select>
                </label>
              ))}
            </div>

            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={handleGenerate}
                disabled={!mapping.descricao}
                className="rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground disabled:opacity-50 sm:py-1.5"
              >
                Confirmar e gerar tickets
              </button>
              <button
                type="button"
                onClick={reset}
                className="rounded-md border px-4 py-2 text-sm sm:py-1.5"
              >
                Cancelar
              </button>
            </div>
          </div>
        )}

        <StateFeedback
          loading={step === 'mapping' && loading}
          error={step === 'mapping' ? error : null}
          loadingLabel="Processando..."
        />
      </div>

      {step === 'done' && tickets && (
        <div className="space-y-3">
          <GeneratedTicketsTable tickets={tickets} />
          <div className="flex flex-wrap gap-2">
            <Link
              to="/kanban"
              className="rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground hover:opacity-90 sm:py-1.5"
            >
              Ir para o Kanban
            </Link>
            <button
              type="button"
              onClick={reset}
              className="rounded-full border px-4 py-2 text-sm hover:bg-accent sm:py-1.5"
            >
              Enviar outro arquivo
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default Ingestao
