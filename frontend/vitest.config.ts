import path from 'node:path'
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// Config separada de vite.config.ts (F7-3) — evita misturar tipos de
// `test` do Vitest na config de dev/build usada pelo servidor real.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    globals: true,
    // Node 22+ expõe um `localStorage`/`sessionStorage` globais nativos
    // (Web Storage API). Sem `--localstorage-file`, essa implementação
    // nativa é um stub sem métodos (`.clear`/`.getItem` etc. undefined).
    // O `populateGlobal` do Vitest só sobrescreve uma chave já presente em
    // `globalThis` se ela estiver na sua allowlist interna — e
    // `localStorage`/`sessionStorage` não estão nessa lista (nesta versão
    // do Vitest) — então o stub nativo do Node vence sobre o
    // `window.localStorage` de verdade do jsdom. Desabilitar o global
    // nativo do Node faz o Vitest usar o do jsdom (funcional) normalmente.
    execArgv: ['--no-experimental-webstorage'],
  },
})
