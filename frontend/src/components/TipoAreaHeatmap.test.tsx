import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { TipoAreaGrade } from '@/lib/api'
import TipoAreaHeatmap from './TipoAreaHeatmap'

const TIPOS = ['Incidente', 'Mudança']
const AREAS = ['Rede', 'Servidor']

function makeGrade(overrides: Partial<TipoAreaGrade> = {}): TipoAreaGrade {
  const celulas = [
    { tipo: 'Incidente', area: 'Rede', total: 132, confianca_media: 0.84 },
    { tipo: 'Incidente', area: 'Servidor', total: 19, confianca_media: 0.86 },
    { tipo: 'Mudança', area: 'Rede', total: 7, confianca_media: 0.69 },
    { tipo: 'Mudança', area: 'Servidor', total: 0, confianca_media: null },
  ]
  return {
    tipos: TIPOS,
    areas: AREAS,
    celulas,
    total: celulas.reduce((soma, c) => soma + c.total, 0),
    sem_area: 3,
    ...overrides,
  }
}

describe('TipoAreaHeatmap', () => {
  it('desenha a grade inteira, inclusive a célula zerada', () => {
    render(<TipoAreaHeatmap grade={makeGrade()} />)

    TIPOS.forEach((tipo) => expect(screen.getByText(tipo)).toBeInTheDocument())
    AREAS.forEach((area) => expect(screen.getByText(area)).toBeInTheDocument())
    expect(screen.getByText('132')).toBeInTheDocument()
    // Célula sem chamado vira um ponto, não um zero solto.
    expect(screen.getByTitle('Mudança em Servidor: nenhum chamado')).toBeInTheDocument()
  })

  it('informa o total e quantos ficaram sem área', () => {
    render(<TipoAreaHeatmap grade={makeGrade()} />)

    expect(screen.getByText(/158 chamados classificados/)).toBeInTheDocument()
    expect(screen.getByText(/3 sem área definida/)).toBeInTheDocument()
  })

  it('alterna para a confiança média ao clicar no botão', async () => {
    render(<TipoAreaHeatmap grade={makeGrade()} limiar={0.75} />)

    await userEvent.click(screen.getByRole('button', { name: /confiança média/i }))

    expect(screen.getByText('0.84')).toBeInTheDocument()
    expect(screen.getByText('0.69')).toBeInTheDocument()
    expect(screen.queryByText('132')).not.toBeInTheDocument()
    expect(screen.getByText(/abaixo do limiar de 0.75/i)).toBeInTheDocument()
  })

  it('mostra aviso quando ainda não há chamado classificado nos dois níveis', () => {
    render(
      <TipoAreaHeatmap
        grade={makeGrade({
          celulas: [{ tipo: 'Incidente', area: 'Rede', total: 0, confianca_media: null }],
          total: 0,
          sem_area: 0,
        })}
      />,
    )

    expect(screen.getByText(/nenhum chamado classificado nos dois níveis/i)).toBeInTheDocument()
  })
})
