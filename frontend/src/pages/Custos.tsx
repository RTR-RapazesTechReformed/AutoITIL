import { useEffect, useState } from 'react'
import { useCurrentUser } from '@/components/RequireAuth'
import { useToast } from '@/lib/toast'
import StatTile from '@/components/StatTile'
import {
  detalharRelatorioCusto,
  fecharPeriodoCusto,
  listarRelatoriosCusto,
  previewCusto,
  type RelatorioCustoDetalhe,
  type RelatorioCustoResumo,
  type PreviewCusto,
} from '@/lib/api'

function formatarCentavos(centavos: number): string {
  return (centavos / 100).toLocaleString('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  })
}

const LABEL_TIPO_EVENTO: Record<string, string> = {
  ingestao_linha: 'Linhas ingeridas',
  classificacao_ticket: 'Tickets classificados',
  enriquecimento_chamada: 'Chamadas de enriquecimento',
}

// Formata a partir dos componentes LOCAIS da data, não toISOString() — que
// converte pra UTC antes de extrair o dia e pode devolver o dia anterior
// dependendo da hora local no momento do clique (ver issue #21).
function formatarDataLocal(d: Date): string {
  const ano = d.getFullYear()
  const mes = String(d.getMonth() + 1).padStart(2, '0')
  const dia = String(d.getDate()).padStart(2, '0')
  return `${ano}-${mes}-${dia}`
}

function Custos() {
  const usuario = useCurrentUser()
  const { showToast } = useToast()
  const [preview, setPreview] = useState<PreviewCusto | null>(null)
  const [relatorios, setRelatorios] = useState<RelatorioCustoResumo[]>([])
  const [relatorioSelecionado, setRelatorioSelecionado] = useState<RelatorioCustoDetalhe | null>(null)
  const [carregando, setCarregando] = useState(true)
  const [fechando, setFechando] = useState(false)

  async function carregar() {
    setCarregando(true)
    try {
      const [previewData, relatoriosData] = await Promise.all([previewCusto(), listarRelatoriosCusto()])
      setPreview(previewData)
      setRelatorios(relatoriosData)
    } catch (err) {
      console.error('Falha ao carregar custos.', err)
      showToast('Falha ao carregar custos.', 'error')
    } finally {
      setCarregando(false)
    }
  }

  useEffect(() => {
    carregar()
  }, [])

  async function handleFecharPeriodo() {
    const hoje = new Date()
    const inicioMesAnterior = new Date(hoje.getFullYear(), hoje.getMonth() - 1, 1)
    const inicioMesAtual = new Date(hoje.getFullYear(), hoje.getMonth(), 1)
    const periodoInicio = formatarDataLocal(inicioMesAnterior)
    const periodoFim = formatarDataLocal(inicioMesAtual)

    setFechando(true)
    try {
      await fecharPeriodoCusto(periodoInicio, periodoFim)
      showToast('Período fechado com sucesso.')
      await carregar()
    } catch (err) {
      console.error('Falha ao fechar período.', err)
      showToast('Falha ao fechar período.', 'error')
    } finally {
      setFechando(false)
    }
  }

  async function handleVerDetalhe(relatorio: RelatorioCustoResumo) {
    try {
      setRelatorioSelecionado(await detalharRelatorioCusto(relatorio.id))
    } catch (err) {
      console.error('Falha ao carregar detalhe do relatório de custo.', err)
      showToast('Falha ao carregar detalhe do relatório de custo.', 'error')
    }
  }

  if (carregando) {
    return <p className="text-sm text-muted-foreground">Carregando custos...</p>
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold">Custos</h1>
        {usuario.is_admin && (
          <button
            type="button"
            onClick={handleFecharPeriodo}
            disabled={fechando}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
          >
            Fechar período anterior
          </button>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatTile
          label="Total do período aberto"
          value={formatarCentavos(preview?.total_centavos ?? 0)}
          destaque
        />
        {preview?.itens.map((item) => (
          <StatTile
            key={item.tipo_evento}
            label={LABEL_TIPO_EVENTO[item.tipo_evento] ?? item.tipo_evento}
            value={String(item.quantidade_total)}
            hint={formatarCentavos(item.custo_total_centavos)}
          />
        ))}
      </div>

      <div>
        <h2 className="mb-2 text-sm font-semibold text-muted-foreground">Relatórios de custo fechados</h2>
        {relatorios.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nenhum relatório de custo fechado ainda.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-muted-foreground">
                <th className="py-2">Período</th>
                <th className="py-2">Status</th>
                <th className="py-2">Total</th>
                <th className="py-2" />
              </tr>
            </thead>
            <tbody>
              {relatorios.map((relatorio) => (
                <tr key={relatorio.id} className="border-t">
                  <td className="py-2">
                    {relatorio.periodo_inicio} – {relatorio.periodo_fim}
                  </td>
                  <td className="py-2">{relatorio.status}</td>
                  <td className="py-2">{formatarCentavos(relatorio.total_centavos)}</td>
                  <td className="py-2">
                    <button onClick={() => handleVerDetalhe(relatorio)} className="text-sm underline">
                      Ver detalhe
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {relatorioSelecionado && (
        <div className="rounded-2xl border bg-card p-4">
          <h3 className="mb-2 text-sm font-semibold">
            Detalhe — {relatorioSelecionado.periodo_inicio} a {relatorioSelecionado.periodo_fim}
          </h3>
          <ul className="flex flex-col gap-1 text-sm">
            {relatorioSelecionado.itens.map((item) => (
              <li key={item.tipo_evento} className="flex justify-between">
                <span>{LABEL_TIPO_EVENTO[item.tipo_evento] ?? item.tipo_evento}</span>
                <span>
                  {item.quantidade_total} × — {formatarCentavos(item.custo_total_centavos)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

export default Custos
