import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { Ticket } from '@/lib/api'
import TicketDetailModal from './TicketDetailModal'

const { enrichTicketMock, reviseTicketClassificationMock, sendEnrichmentFeedbackMock } = vi.hoisted(() => ({
  enrichTicketMock: vi.fn(),
  reviseTicketClassificationMock: vi.fn(),
  sendEnrichmentFeedbackMock: vi.fn(),
}))

vi.mock('@/lib/api', () => ({
  enrichTicket: enrichTicketMock,
  reviseTicketClassification: reviseTicketClassificationMock,
  sendEnrichmentFeedback: sendEnrichmentFeedbackMock,
}))

beforeEach(() => {
  enrichTicketMock.mockReset()
  reviseTicketClassificationMock.mockReset()
  sendEnrichmentFeedbackMock.mockReset()
})

function makeTicket(overrides: Partial<Ticket> = {}): Ticket {
  return {
    id: 1,
    codigo: 'TCK-0001',
    titulo_sugerido: 'VPN caiu para o escritório',
    descricao_enriquecida: null,
    tipo_itil: 'Incidente',
    area_responsavel: 'Rede',
    prioridade: 'P2',
    status: 'triagem',
    confianca_n1: 0.9,
    confianca_n2: 0.85,
    data_geracao: '2026-08-01T10:00:00Z',
    atualizado_em: '2026-08-01T10:00:00Z',
    feedback_enriquecimento: null,
    ...overrides,
  }
}

describe('TicketDetailModal', () => {
  it('não renderiza conteúdo quando open é false', () => {
    render(
      <TicketDetailModal
        ticket={makeTicket()}
        open={false}
        onOpenChange={vi.fn()}
        onEnriched={vi.fn()}
        onRevised={vi.fn()}
        onFeedback={vi.fn()}
      />,
    )

    expect(screen.queryByText('TCK-0001')).not.toBeInTheDocument()
  })

  it('mostra os metadados do ticket quando aberto', () => {
    render(
      <TicketDetailModal
        ticket={makeTicket()}
        open={true}
        onOpenChange={vi.fn()}
        onEnriched={vi.fn()}
        onRevised={vi.fn()}
        onFeedback={vi.fn()}
      />,
    )

    expect(screen.getByText('TCK-0001')).toBeInTheDocument()
    expect(screen.getByText('Incidente')).toBeInTheDocument()
    expect(screen.getByText('Rede')).toBeInTheDocument()
  })

  it('fecha o modal ao clicar no botão de fechar', async () => {
    const onOpenChange = vi.fn()

    render(
      <TicketDetailModal
        ticket={makeTicket()}
        open={true}
        onOpenChange={onOpenChange}
        onEnriched={vi.fn()}
        onRevised={vi.fn()}
        onFeedback={vi.fn()}
      />,
    )

    await userEvent.click(screen.getByRole('button', { name: 'Fechar' }))

    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it('mostra o status humanizado, não o código interno cru', () => {
    render(
      <TicketDetailModal
        ticket={makeTicket({ status: 'a_fazer' })}
        open={true}
        onOpenChange={vi.fn()}
        onEnriched={vi.fn()}
        onRevised={vi.fn()}
        onFeedback={vi.fn()}
      />,
    )

    expect(screen.getByText('A Fazer')).toBeInTheDocument()
    expect(screen.queryByText('a_fazer')).not.toBeInTheDocument()
  })

  it('mostra o botão de enriquecer quando ainda não há descrição enriquecida', () => {
    render(
      <TicketDetailModal
        ticket={makeTicket({ descricao_enriquecida: null })}
        open={true}
        onOpenChange={vi.fn()}
        onEnriched={vi.fn()}
        onRevised={vi.fn()}
        onFeedback={vi.fn()}
      />,
    )

    expect(screen.getByRole('button', { name: 'Enriquecer descrição' })).toBeInTheDocument()
  })

  it('mostra os três campos estruturados quando já há descrição enriquecida', () => {
    render(
      <TicketDetailModal
        ticket={makeTicket({
          descricao_enriquecida: {
            objetivo: 'Resolver a VPN.',
            requisicoes: ['Verificar configuração.', 'Testar conectividade.'],
            cargo_recomendado: 'Suporte de redes.',
          },
        })}
        open={true}
        onOpenChange={vi.fn()}
        onEnriched={vi.fn()}
        onRevised={vi.fn()}
        onFeedback={vi.fn()}
      />,
    )

    expect(screen.getByText('Resolver a VPN.')).toBeInTheDocument()
    expect(screen.getByText('Verificar configuração.')).toBeInTheDocument()
    expect(screen.getByText('Testar conectividade.')).toBeInTheDocument()
    expect(screen.getByText('Suporte de redes.')).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Enriquecer descrição' }),
    ).not.toBeInTheDocument()
  })

  it('mostra o fallback quando requisicoes está vazio ou nulo, sem crashar', () => {
    render(
      <TicketDetailModal
        ticket={makeTicket({
          descricao_enriquecida: {
            objetivo: 'Resolver a VPN.',
            requisicoes: [],
            cargo_recomendado: 'Suporte de redes.',
          },
        })}
        open={true}
        onOpenChange={vi.fn()}
        onEnriched={vi.fn()}
        onRevised={vi.fn()}
        onFeedback={vi.fn()}
      />,
    )

    expect(screen.getAllByText('Não informado pelo modelo.').length).toBeGreaterThan(0)
  })

  it('chama a API e o callback onEnriched ao clicar no botão', async () => {
    enrichTicketMock.mockResolvedValue({
      id: 1,
      descricao_enriquecida: {
        objetivo: 'Resolver a VPN.',
        requisicoes: ['Verificar configuração.'],
        cargo_recomendado: 'Suporte de redes.',
      },
    })
    const onEnriched = vi.fn()

    render(
      <TicketDetailModal
        ticket={makeTicket()}
        open={true}
        onOpenChange={vi.fn()}
        onEnriched={onEnriched}
        onRevised={vi.fn()}
        onFeedback={vi.fn()}
      />,
    )

    await userEvent.click(screen.getByRole('button', { name: 'Enriquecer descrição' }))

    await waitFor(() =>
      expect(onEnriched).toHaveBeenCalledWith(1, {
        objetivo: 'Resolver a VPN.',
        requisicoes: ['Verificar configuração.'],
        cargo_recomendado: 'Suporte de redes.',
      }),
    )
    expect(enrichTicketMock).toHaveBeenCalledWith(1)
  })

  it('mostra mensagem de erro quando a chamada falha', async () => {
    enrichTicketMock.mockRejectedValue(new Error('falhou'))

    render(
      <TicketDetailModal
        ticket={makeTicket()}
        open={true}
        onOpenChange={vi.fn()}
        onEnriched={vi.fn()}
        onRevised={vi.fn()}
        onFeedback={vi.fn()}
      />,
    )

    await userEvent.click(screen.getByRole('button', { name: 'Enriquecer descrição' }))

    await waitFor(() =>
      expect(screen.getByText('Falha ao gerar descrição enriquecida.')).toBeInTheDocument(),
    )
  })

  it('o chip de Tipo mostra o valor atual e abre a lista de opções ao clicar', async () => {
    render(
      <TicketDetailModal
        ticket={makeTicket({ tipo_itil: 'Incidente' })}
        open={true}
        onOpenChange={vi.fn()}
        onEnriched={vi.fn()}
        onRevised={vi.fn()}
        onFeedback={vi.fn()}
      />,
    )

    const chip = screen.getByRole('combobox', { name: 'Revisar Tipo' })
    expect(chip).toHaveTextContent('Incidente')

    await userEvent.click(chip)

    expect(screen.getByRole('option', { name: 'Problema' })).toBeInTheDocument()
  })

  it('escolher uma opção no chip de Tipo dispara a revisão e atualiza o ticket', async () => {
    const ticketRevisado: Ticket = { ...makeTicket(), tipo_itil: 'Problema' }
    reviseTicketClassificationMock.mockResolvedValue(ticketRevisado)
    const onRevised = vi.fn()

    render(
      <TicketDetailModal
        ticket={makeTicket()}
        open={true}
        onOpenChange={vi.fn()}
        onEnriched={vi.fn()}
        onRevised={onRevised}
        onFeedback={vi.fn()}
      />,
    )

    await userEvent.click(screen.getByRole('combobox', { name: 'Revisar Tipo' }))
    await userEvent.click(screen.getByRole('option', { name: 'Problema' }))

    await waitFor(() => expect(onRevised).toHaveBeenCalledWith(1, ticketRevisado))
    expect(reviseTicketClassificationMock).toHaveBeenCalledWith(1, 'tipo_itil', 'Problema')
  })

  it('confirmar o mesmo valor de Área também dispara a revisão', async () => {
    reviseTicketClassificationMock.mockResolvedValue(makeTicket())
    const onRevised = vi.fn()

    render(
      <TicketDetailModal
        ticket={makeTicket({ area_responsavel: 'Rede' })}
        open={true}
        onOpenChange={vi.fn()}
        onEnriched={vi.fn()}
        onRevised={onRevised}
        onFeedback={vi.fn()}
      />,
    )

    await userEvent.click(screen.getByRole('combobox', { name: 'Revisar Área' }))
    // escolhe a mesma opção já mostrada no chip — Radix chama
    // onValueChange mesmo repetindo o valor atual (diferente de um
    // <select> nativo), então a revisão deve disparar do mesmo jeito.
    await userEvent.click(screen.getByRole('option', { name: 'Rede' }))

    await waitFor(() => expect(onRevised).toHaveBeenCalled())
    expect(reviseTicketClassificationMock).toHaveBeenCalledWith(1, 'area', 'Rede')
  })

  it('mostra mensagem de erro quando a revisão falha', async () => {
    reviseTicketClassificationMock.mockRejectedValue(new Error('falhou'))

    render(
      <TicketDetailModal
        ticket={makeTicket()}
        open={true}
        onOpenChange={vi.fn()}
        onEnriched={vi.fn()}
        onRevised={vi.fn()}
        onFeedback={vi.fn()}
      />,
    )

    await userEvent.click(screen.getByRole('combobox', { name: 'Revisar Tipo' }))
    await userEvent.click(screen.getByRole('option', { name: 'Problema' }))

    await waitFor(() =>
      expect(screen.getByText('Falha ao registrar revisão.')).toBeInTheDocument(),
    )
  })

  it('não mostra os botões de feedback quando não há enriquecimento', () => {
    render(
      <TicketDetailModal
        ticket={makeTicket({ descricao_enriquecida: null })}
        open={true}
        onOpenChange={vi.fn()}
        onEnriched={vi.fn()}
        onRevised={vi.fn()}
        onFeedback={vi.fn()}
      />,
    )

    expect(
      screen.queryByRole('button', { name: 'Marcar enriquecimento como bom' }),
    ).not.toBeInTheDocument()
  })

  it('mostra os botões de feedback quando há enriquecimento, sem voto marcado', () => {
    render(
      <TicketDetailModal
        ticket={makeTicket({
          descricao_enriquecida: {
            objetivo: 'Resolver a VPN.',
            requisicoes: ['Verificar configuração.'],
            cargo_recomendado: 'Suporte de redes.',
          },
        })}
        open={true}
        onOpenChange={vi.fn()}
        onEnriched={vi.fn()}
        onRevised={vi.fn()}
        onFeedback={vi.fn()}
      />,
    )

    const botaoUp = screen.getByRole('button', { name: 'Marcar enriquecimento como bom' })
    const botaoDown = screen.getByRole('button', { name: 'Marcar enriquecimento como ruim' })
    expect(botaoUp).toHaveAttribute('aria-pressed', 'false')
    expect(botaoDown).toHaveAttribute('aria-pressed', 'false')
  })

  it('clicar em 👍 chama a API e propaga onFeedback', async () => {
    const ticketAtualizado: Ticket = { ...makeTicket(), feedback_enriquecimento: 'up' }
    sendEnrichmentFeedbackMock.mockResolvedValue(ticketAtualizado)
    const onFeedback = vi.fn()

    render(
      <TicketDetailModal
        ticket={makeTicket({
          descricao_enriquecida: {
            objetivo: 'Resolver a VPN.',
            requisicoes: ['Verificar configuração.'],
            cargo_recomendado: 'Suporte de redes.',
          },
        })}
        open={true}
        onOpenChange={vi.fn()}
        onEnriched={vi.fn()}
        onRevised={vi.fn()}
        onFeedback={onFeedback}
      />,
    )

    await userEvent.click(screen.getByRole('button', { name: 'Marcar enriquecimento como bom' }))

    await waitFor(() => expect(onFeedback).toHaveBeenCalledWith(1, ticketAtualizado))
    expect(sendEnrichmentFeedbackMock).toHaveBeenCalledWith(1, 'up')
  })

  it('clicar no voto já ativo não chama a API', async () => {
    render(
      <TicketDetailModal
        ticket={makeTicket({
          descricao_enriquecida: {
            objetivo: 'Resolver a VPN.',
            requisicoes: ['Verificar configuração.'],
            cargo_recomendado: 'Suporte de redes.',
          },
          feedback_enriquecimento: 'up',
        })}
        open={true}
        onOpenChange={vi.fn()}
        onEnriched={vi.fn()}
        onRevised={vi.fn()}
        onFeedback={vi.fn()}
      />,
    )

    await userEvent.click(screen.getByRole('button', { name: 'Marcar enriquecimento como bom' }))

    expect(sendEnrichmentFeedbackMock).not.toHaveBeenCalled()
  })

  it('mostra mensagem de erro quando o feedback falha', async () => {
    sendEnrichmentFeedbackMock.mockRejectedValue(new Error('falhou'))

    render(
      <TicketDetailModal
        ticket={makeTicket({
          descricao_enriquecida: {
            objetivo: 'Resolver a VPN.',
            requisicoes: ['Verificar configuração.'],
            cargo_recomendado: 'Suporte de redes.',
          },
        })}
        open={true}
        onOpenChange={vi.fn()}
        onEnriched={vi.fn()}
        onRevised={vi.fn()}
        onFeedback={vi.fn()}
      />,
    )

    await userEvent.click(screen.getByRole('button', { name: 'Marcar enriquecimento como bom' }))

    await waitFor(() =>
      expect(screen.getByText('Falha ao registrar feedback.')).toBeInTheDocument(),
    )
  })
})
