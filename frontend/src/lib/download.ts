/** Dispara o download de um Blob no browser via link temporário — mesmo
 * padrão vanilla usado por qualquer SPA que baixa um arquivo já em memória
 * (resultado de fetch), sem precisar de uma navegação real. */
export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}
