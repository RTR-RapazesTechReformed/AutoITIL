type StatTileProps = {
  label: string
  value: string
  /** Contexto abaixo do número: comparação, unidade derivada, denominador.
   *  Um valor sozinho ("198") raramente informa; o que informa é o que ele
   *  significa ("de 220 linhas lidas"). */
  hint?: string
  /** Ênfase visual para o número que a seção existe para comunicar. */
  destaque?: boolean
}

/** Tile de número único, compartilhado entre Dashboard e Métricas.
 *  Extraído do StatTile local do Dashboard quando a aba Técnicas passou a
 *  precisar do mesmo formato — mantê-los separados garantia divergência. */
function StatTile({ label, value, hint, destaque = false }: StatTileProps) {
  return (
    <div
      className={`rounded-lg border bg-card p-4 shadow-sm ${
        destaque ? 'border-primary/40' : ''
      }`}
    >
      <p className="text-sm text-muted-foreground">{label}</p>
      <p
        className={`mt-1 font-semibold tabular-nums ${
          destaque ? 'text-3xl' : 'text-2xl'
        }`}
      >
        {value}
      </p>
      {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
    </div>
  )
}

export default StatTile
