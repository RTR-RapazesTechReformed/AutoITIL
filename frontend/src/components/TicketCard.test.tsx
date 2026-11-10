import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { DndContext } from '@dnd-kit/core'
import type { Ticket } from '@/lib/api'
import TicketCard from './TicketCard'

const { enrichTicketMock } = vi.hoisted(() => ({ enrichTicketMock: vi.fn() }))

vi.mock('@/lib/api', () => ({ enrichTicket: enrichTicketMock }))

beforeEach(() => {
  enrichTicketMock.mockReset()
})

// useDraggable exige um DndContext ancestral — sem ele o hook falha em runtime.
function renderCard(ticket: Ticket, onEnriched?: (id: number, fields: unknown) => void) {
  return render(
    <DndContext>
      <TicketCard ticket={ticket} onEnriched={onEnriched} />
    </DndContext>,
  )
}

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

describe('TicketCard', () => {
  it('renderiza código, título, prioridade e área do ticket', () => {
    renderCard(makeTicket())

    expect(screen.getByText('TCK-0001')).toBeInTheDocument()
    expect(screen.getByText('VPN caiu para o escritório')).toBeInTheDocument()
    expect(screen.getByText('P2')).toBeInTheDocument()
    expect(screen.getByText('Rede')).toBeInTheDocument()
  })

  it('mostra "—" quando area_responsavel é null', () => {
    renderCard(makeTicket({ area_responsavel: null }))

    expect(screen.getByText('—')).toBeInTheDocument()
  })

  it('sinaliza "baixa confiança" quando confianca_n1 está abaixo do limiar', () => {
    renderCard(makeTicket({ confianca_n1: 0.5 }))

    expect(screen.getByText('baixa confiança')).toBeInTheDocument()
  })

  it('não sinaliza baixa confiança quando confianca_n1 está no limiar ou acima', () => {
    renderCard(makeTicket({ confianca_n1: 0.9 }))

    expect(screen.queryByText('baixa confiança')).not.toBeInTheDocument()
  })

  it('não sinaliza baixa confiança quando confianca_n1 é null (sem classificação BERT)', () => {
    renderCard(makeTicket({ confianca_n1: null }))

    expect(screen.queryByText('baixa confiança')).not.toBeInTheDocument()
  })

  it('mostra o título sugerido quando ainda não há descrição enriquecida', () => {
    renderCard(makeTicket({ descricao_enriquecida: null }))

    expect(screen.getByText('VPN caiu para o escritório')).toBeInTheDocument()
  })

  it('mostra o campo objetivo em vez do título quando já há descrição enriquecida', () => {
    renderCard(
      makeTicket({
        descricao_enriquecida: {
          objetivo: 'Resolver a VPN que não conecta.',
          requisicoes: null,
          cargo_recomendado: null,
        },
      }),
    )

    expect(screen.getByText('Resolver a VPN que não conecta.')).toBeInTheDocument()
    expect(screen.queryByText('VPN caiu para o escritório')).not.toBeInTheDocument()
  })

  it('não mostra mais o botão de enriquecer no card compacto', () => {
    renderCard(makeTicket({ descricao_enriquecida: null }))

    expect(
      screen.queryByRole('button', { name: 'Enriquecer descrição' }),
    ).not.toBeInTheDocument()
  })

  it('abre o modal de detalhes ao clicar no ícone de expandir', async () => {
    renderCard(makeTicket())

    expect(screen.queryByText('Tipo')).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Expandir card' }))

    expect(screen.getByText('Tipo')).toBeInTheDocument()
  })

  // Regressão: DialogPortal move o DOM do modal pra fora do card, mas não
  // tira o componente da árvore React — sem stopPropagation em
  // TicketDetailModal, um pointerdown dentro do modal (ex.: no botão de
  // enriquecer) borbulha pelos listeners do useDraggable do card por trás e
  // dispara um drag real.
  it('não inicia drag do card ao interagir com um elemento dentro do modal', async () => {
    const onDragStart = vi.fn()

    render(
      <DndContext onDragStart={onDragStart}>
        <TicketCard ticket={makeTicket()} />
      </DndContext>,
    )

    await userEvent.click(screen.getByRole('button', { name: 'Expandir card' }))

    const enrichButton = screen.getByRole('button', { name: 'Enriquecer descrição' })
    fireEvent.pointerDown(enrichButton, { pointerId: 1, button: 0, isPrimary: true })
    fireEvent.pointerMove(document, { pointerId: 1, clientX: 20, clientY: 20 })

    expect(onDragStart).not.toHaveBeenCalled()
  })

  // Regressão: sem <DragOverlay> (ver TicketCardOverlay/Kanban.tsx), este
  // componente aplicava o transform de arraste direto neste elemento — o
  // que o prendia no contexto de overflow/stacking da raia de origem
  // (bug de scroll X/Y indevido e card "por baixo" de outra raia). Agora
  // ele só recebe opacidade reduzida como placeholder; quem se move é o
  // card fantasma renderizado pelo DragOverlay, fora dessa raia.
  it('não aplica transform inline no card durante o drag, só opacidade reduzida', async () => {
    const onDragStart = vi.fn()

    render(
      <DndContext onDragStart={onDragStart}>
        <TicketCard ticket={makeTicket()} />
      </DndContext>,
    )

    const card = screen.getByText('TCK-0001').closest('[role="button"]') as HTMLElement
    fireEvent.pointerDown(card, { pointerId: 1, button: 0, isPrimary: true, clientX: 0, clientY: 0 })
    fireEvent.pointerMove(document, { pointerId: 1, clientX: 50, clientY: 50 })

    expect(onDragStart).toHaveBeenCalled()
    expect(card.style.transform).toBe('')
    expect(card.className).toContain('opacity-30')
  })
})
