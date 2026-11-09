import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { clearToken, setToken } from './auth'

const fetchMock = vi.fn()

beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock)
  fetchMock.mockReset()
  clearToken()
  vi.resetModules()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('request()', () => {
  it('inclui o header Authorization quando há token salvo', async () => {
    setToken('token-de-teste')
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ status: 'ok' }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    )

    const { getMetrics } = await import('./api')
    await getMetrics()

    const [, init] = fetchMock.mock.calls[0]
    const headers = new Headers(init.headers)
    expect(headers.get('Authorization')).toBe('Bearer token-de-teste')
  })

  it('limpa o token e redireciona para /login numa resposta 401', async () => {
    setToken('token-expirado')
    fetchMock.mockResolvedValue(
      new Response(
        JSON.stringify({ error: { code: 'UNAUTHORIZED', message: 'Token inválido.' } }),
        { status: 401, headers: { 'content-type': 'application/json' } },
      ),
    )
    window.location.href = ''

    const { getMetrics } = await import('./api')
    await expect(getMetrics()).rejects.toThrow()

    expect(localStorage.getItem('autoitil-auth-token')).toBeNull()
    expect(window.location.href).toContain('/login')
  })

  it('não redireciona quando a falha 401 é do próprio /api/auth/login', async () => {
    fetchMock.mockResolvedValue(
      new Response(
        JSON.stringify({
          success: false,
          error: { code: 'INVALID_CREDENTIALS', message: 'Email ou senha inválidos.' },
        }),
        { status: 401, headers: { 'content-type': 'application/json' } },
      ),
    )
    window.location.href = ''

    const { login } = await import('./api')
    await expect(login('a@a.com', 'errada')).rejects.toThrow()

    expect(window.location.href).toBe('')
  })
})

describe('generateTicketsFromFile()', () => {
  // Regressão: a rota virou autenticada (movida pra /api/tickets/generate-from-file
  // na remoção do fluxo legado em Jinja2)
  // — sem este teste, um fetch() sem o header Authorization não quebraria nenhum outro teste
  // (Ingestao.test.tsx mocka generateTicketsFromFile por inteiro).
  it('chama /api/tickets/generate-from-file com o header Authorization', async () => {
    setToken('token-de-teste')
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    )

    const { generateTicketsFromFile } = await import('./api')
    await generateTicketsFromFile({ filePath: 'uploads/x.csv', descricao: 'descricao' })

    const [path, init] = fetchMock.mock.calls[0]
    expect(path).toBe('/api/tickets/generate-from-file')
    const headers = new Headers(init.headers)
    expect(headers.get('Authorization')).toBe('Bearer token-de-teste')
  })

  it('numa resposta de erro sem corpo JSON (ex.: timeout de proxy), usa a mensagem genérica em vez de explodir', async () => {
    fetchMock.mockResolvedValue(
      new Response('<html>504 Gateway Timeout</html>', {
        status: 504,
        headers: { 'content-type': 'text/html' },
      }),
    )

    const { generateTicketsFromFile } = await import('./api')

    await expect(
      generateTicketsFromFile({ filePath: 'uploads/x.csv', descricao: 'descricao' }),
    ).rejects.toMatchObject({ status: 504, message: 'Falha ao gerar os tickets.' })
  })
})
