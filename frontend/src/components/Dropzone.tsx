import { useId, useRef, useState } from 'react'
import { UploadCloud } from 'lucide-react'
import { cn } from '@/lib/utils'

type Props = {
  accept: string
  hint: string
  disabled?: boolean
  onFileSelected: (file: File) => void
}

// V2 — Direção A "Pastel Flutuante": estrutura
// inspirada em frontend/screens/drag_and_drop_example.jpg (dropzone com
// ícone circular + drag real), mas sem o fundo em gradiente da referência
// — isso pertence à Direção B "Vidro & Gradiente", não à que escolhemos.
// Aqui o dropzone flutua sobre o --background liso, com o acento único
// --primary no lugar do rosa/roxo saturado do original.
function Dropzone({ accept, hint, disabled, onFileSelected }: Props) {
  const [isDragging, setIsDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const inputId = useId()

  function handleDragOver(event: React.DragEvent<HTMLDivElement>) {
    event.preventDefault()
    if (disabled) return
    setIsDragging(true)
  }

  function handleDragLeave(event: React.DragEvent<HTMLDivElement>) {
    // Ignora dragleave disparado ao entrar num filho do dropzone —
    // só desativa o estado quando o ponteiro sai da área inteira.
    if (event.currentTarget.contains(event.relatedTarget as Node)) return
    setIsDragging(false)
  }

  function handleDrop(event: React.DragEvent<HTMLDivElement>) {
    event.preventDefault()
    setIsDragging(false)
    if (disabled) return
    const file = event.dataTransfer.files?.[0]
    if (file) onFileSelected(file)
  }

  function handleInputChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (file) onFileSelected(file)
    event.target.value = '' // permite selecionar o mesmo arquivo de novo após um erro
  }

  return (
    <div
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={cn(
        // bg-card fica fixo (nunca muda pra --accent) de propósito: com
        // --primary só passando 4.66:1 em branco puro, qualquer superfície
        // um pouco mais escura derrubava o texto do link abaixo de 4.5:1.
        // O estado de arraste é só borda + ring, sem trocar o fundo.
        'flex flex-col items-center gap-3 rounded-2xl border-2 border-dashed bg-card p-10 text-center transition-colors',
        isDragging ? 'border-primary ring-2 ring-primary/20' : 'border-border',
        disabled && 'pointer-events-none opacity-60',
      )}
    >
      <span className="flex size-12 items-center justify-center rounded-full bg-accent text-primary">
        <UploadCloud className="size-6" strokeWidth={2} aria-hidden="true" />
      </span>

      <p className="text-sm">
        <label htmlFor={inputId} className="cursor-pointer font-medium text-primary hover:underline">
          Clique para escolher um arquivo
        </label>{' '}
        <span className="text-muted-foreground">ou arraste e solte aqui.</span>
      </p>
      <p className="text-xs text-muted-foreground">{hint}</p>

      <input
        ref={inputRef}
        id={inputId}
        type="file"
        accept={accept}
        disabled={disabled}
        onChange={handleInputChange}
        className="sr-only"
      />
    </div>
  )
}

export default Dropzone
