import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Dropzone from './Dropzone'

function makeFile(name = 'tickets.csv') {
  return new File(['a,b\n1,2'], name, { type: 'text/csv' })
}

describe('Dropzone', () => {
  it('mostra o rótulo e a dica passada', () => {
    render(<Dropzone accept=".csv,.xlsx" hint="Máx. 10MB, 5000 linhas." onFileSelected={vi.fn()} />)

    expect(screen.getByText(/clique para escolher um arquivo/i)).toBeInTheDocument()
    expect(screen.getByText('Máx. 10MB, 5000 linhas.')).toBeInTheDocument()
  })

  it('chama onFileSelected ao escolher um arquivo pelo input', async () => {
    const onFileSelected = vi.fn()
    render(<Dropzone accept=".csv,.xlsx" hint="Máx. 10MB." onFileSelected={onFileSelected} />)

    const file = makeFile()
    const input = screen.getByLabelText(/clique para escolher um arquivo/i) as HTMLInputElement
    await userEvent.upload(input, file)

    expect(onFileSelected).toHaveBeenCalledWith(file)
  })

  it('chama onFileSelected ao soltar um arquivo (drop)', () => {
    const onFileSelected = vi.fn()
    const { container } = render(
      <Dropzone accept=".csv,.xlsx" hint="Máx. 10MB." onFileSelected={onFileSelected} />,
    )

    const file = makeFile('planilha.xlsx')
    const dropzone = container.firstChild as HTMLElement
    fireEvent.drop(dropzone, { dataTransfer: { files: [file] } })

    expect(onFileSelected).toHaveBeenCalledWith(file)
  })

  it('não chama onFileSelected quando disabled', () => {
    const onFileSelected = vi.fn()
    const { container } = render(
      <Dropzone accept=".csv,.xlsx" hint="Máx. 10MB." disabled onFileSelected={onFileSelected} />,
    )

    const dropzone = container.firstChild as HTMLElement
    fireEvent.drop(dropzone, { dataTransfer: { files: [makeFile()] } })

    expect(onFileSelected).not.toHaveBeenCalled()
  })
})
