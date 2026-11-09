import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { GeneratedTicket } from '@/lib/api'
import GeneratedTicketsTable from './GeneratedTicketsTable'

function makeTicket(overrides: Partial<GeneratedTicket> = {}): GeneratedTicket {
  return {
    id_ticket: 'TCK-0001',
    titulo_sugerido: 'VPN não conecta',
    tipo_itil: 'Incidente',
    area_responsavel: 'Rede',
    prioridade: 'P1',
    descricao_original: 'vpn nao conecta',
    data_geracao: '2026-08-01T10:00:00Z',
    id_origem: 'L0001',
    confianca_n1: 0.94,
    confianca_n2: 0.9,
    ...overrides,
  }
}

describe('GeneratedTicketsTable', () => {
  it('mostra a contagem e uma linha por ticket', () => {
    render(
      <GeneratedTicketsTable
        tickets={[makeTicket(), makeTicket({ id_ticket: 'TCK-0002', titulo_sugerido: 'Impressora sem tinta' })]}
      />,
    )

    expect(screen.getByText('2 tickets gerados e salvos com sucesso.')).toBeInTheDocument()
    expect(screen.getByText('TCK-0001')).toBeInTheDocument()
    expect(screen.getByText('TCK-0002')).toBeInTheDocument()
    expect(screen.getByText('Impressora sem tinta')).toBeInTheDocument()
  })

  it('usa singular quando há só um ticket', () => {
    render(<GeneratedTicketsTable tickets={[makeTicket()]} />)

    expect(screen.getByText('1 ticket gerado e salvo com sucesso.')).toBeInTheDocument()
  })

  it('sinaliza confiança abaixo do limiar com destaque', () => {
    render(<GeneratedTicketsTable tickets={[makeTicket({ confianca_n1: 0.5 })]} />)

    expect(screen.getByText('50%')).toHaveClass('text-destructive')
  })

  it('não destaca confiança acima do limiar', () => {
    render(<GeneratedTicketsTable tickets={[makeTicket({ confianca_n1: 0.94 })]} />)

    expect(screen.getByText('94%')).not.toHaveClass('text-destructive')
  })

  it('filtra por código ou título ao digitar na busca', async () => {
    render(
      <GeneratedTicketsTable
        tickets={[
          makeTicket({ id_ticket: 'TCK-0001', titulo_sugerido: 'VPN não conecta' }),
          makeTicket({ id_ticket: 'TCK-0002', titulo_sugerido: 'Impressora sem tinta' }),
        ]}
      />,
    )

    await userEvent.type(screen.getByPlaceholderText(/buscar por código ou título/i), 'impressora')

    expect(screen.queryByText('VPN não conecta')).not.toBeInTheDocument()
    expect(screen.getByText('Impressora sem tinta')).toBeInTheDocument()
  })

  it('mostra mensagem de vazio quando a busca não encontra nada', async () => {
    render(<GeneratedTicketsTable tickets={[makeTicket()]} />)

    await userEvent.type(screen.getByPlaceholderText(/buscar por código ou título/i), 'xyz123')

    expect(screen.getByText(/nenhum ticket encontrado/i)).toBeInTheDocument()
  })
})
