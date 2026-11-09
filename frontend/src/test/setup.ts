import '@testing-library/jest-dom/vitest'

// radix-ui's Select (Content/Viewport) chama essas APIs de DOM que o
// jsdom não implementa — necessário desde que Select passou a ser usado
// (ver frontend/src/components/ui/select.tsx).
if (!Element.prototype.hasPointerCapture) {
  Element.prototype.hasPointerCapture = () => false
}
if (!Element.prototype.setPointerCapture) {
  Element.prototype.setPointerCapture = () => {}
}
if (!Element.prototype.releasePointerCapture) {
  Element.prototype.releasePointerCapture = () => {}
}
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {}
}

// jsdom não implementa navegação real: atribuir `window.location.href`
// dispara o algoritmo de navegação do jsdom, que aborta com "Not
// implemented: navigation to another Document" e não atualiza `href`.
// Isso é necessário pro fluxo de logout em src/lib/api.ts (redireciona pra
// /login numa resposta 401) e é testado literalmente atribuindo/lendo
// `window.location.href` em src/lib/api.test.ts — substitui `location` por
// um objeto simples e gravável só pra permitir essa leitura/escrita nos
// testes (não faz navegação de verdade, o que os testes não precisam).
Object.defineProperty(globalThis, 'location', {
  configurable: true,
  enumerable: true,
  writable: true,
  value: { ...window.location, href: window.location.href },
})
