import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ApiRequestError, login } from '@/lib/api'
import { setToken } from '@/lib/auth'
import { Button } from '@/components/ui/button'
import ThemeToggle from '@/components/ThemeToggle'
import { PRIORITY_STYLES } from '@/lib/priority'

// V2 — Direção A "Pastel Flutuante": split-screen com
// uma coluna de branding, escolhida entre 2 opções comparadas visualmente
// (a outra era o mesmo fundo pontilhado da Landing com um card central) —
// decisão do usuário. Fora do `Layout` operacional, igual à Landing: sem
// sidebar, com `ThemeToggle` próprio.
function Login() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [senha, setSenha] = useState('')
  const [erro, setErro] = useState<string | null>(null)
  const [carregando, setCarregando] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setErro(null)
    setCarregando(true)
    try {
      const resposta = await login(email, senha)
      setToken(resposta.access_token)
      navigate('/ingestao')
    } catch (err) {
      const mensagem = err instanceof ApiRequestError ? err.message : 'Falha ao entrar.'
      setErro(mensagem)
    } finally {
      setCarregando(false)
    }
  }

  return (
    <div className="grid min-h-screen md:grid-cols-2">
      {/* Coluna de branding — reaproveita o visual da Landing quase ao pé da
          letra (mesmos dois cards flutuantes rotacionados, mesmos blobs,
          mesmo pontilhado), em vez do bloco sólido `bg-primary` da primeira
          tentativa: um preenchimento cheio de marca destoava de toda a
          identidade "Pastel Flutuante" (cor como acento, não como bloco) e
          fazia a tela parecer de outro produto (achado do usuário
          comparando as duas telas lado a lado). `bg-muted` em vez de
          `bg-background` só pra existir alguma partição entre as colunas —
          são tons vizinhos na paleta, não um contraste forte. Some em telas
          estreitas pra não roubar espaço do formulário no celular. */}
      <div className="relative hidden flex-col justify-between overflow-hidden bg-muted p-10 md:flex">
        <div
          aria-hidden="true"
          className="absolute inset-0"
          style={{
            backgroundImage:
              'radial-gradient(circle, color-mix(in srgb, var(--primary) 18%, transparent) 1.5px, transparent 1.5px)',
            backgroundSize: '18px 18px',
          }}
        />
        <div
          aria-hidden="true"
          className="absolute top-8 -right-10 h-56 w-56 rounded-full bg-[color-mix(in_srgb,var(--chart-7)_45%,transparent)] blur-2xl"
        />
        <div
          aria-hidden="true"
          className="absolute -bottom-16 -left-10 h-56 w-56 rounded-full bg-[color-mix(in_srgb,var(--primary)_35%,transparent)] blur-2xl"
        />

        <span className="relative font-semibold">AutoITIL</span>

        <div className="relative flex flex-1 items-center" aria-hidden="true">
          <div className="w-full max-w-xs">
            <div className="relative rotate-[-4deg] rounded-2xl border bg-card p-4 shadow-sm">
              <p className="text-xs text-muted-foreground">TCK-0142 · Rede</p>
              <p className="mt-1 text-sm font-medium">VPN não conecta desde ontem</p>
              <span
                className={`mt-2 inline-block rounded-full px-2 py-0.5 text-[11px] font-medium ${PRIORITY_STYLES.P1}`}
              >
                P1
              </span>
            </div>
            <div className="relative mt-4 ml-12 max-w-[14rem] rotate-[3deg] rounded-2xl border bg-card p-4 shadow-sm">
              <p className="text-xs text-muted-foreground">Confiança média (N1)</p>
              <p className="mt-1 text-2xl font-semibold tabular-nums">0.91</p>
            </div>
          </div>
        </div>

        <div className="relative max-w-sm">
          <h1 className="text-2xl leading-tight font-bold text-balance">
            Triagem de tickets de TI, automática e rastreável
          </h1>
          <p className="mt-3 text-sm text-muted-foreground">
            Suba uma planilha, deixe o modelo classificar tipo ITIL e área responsável,
            acompanhe tudo no Kanban.
          </p>
        </div>
      </div>

      {/* Coluna do formulário */}
      <div className="flex flex-col justify-center bg-background px-6 py-10 sm:px-10">
        <div className="mx-auto w-full max-w-sm">
          <div className="mb-6 flex items-center justify-between md:hidden">
            <Link to="/" className="font-semibold">
              AutoITIL
            </Link>
            <ThemeToggle />
          </div>
          <div className="mb-6 hidden justify-end md:flex">
            <ThemeToggle />
          </div>

          <div className="rounded-2xl border bg-card p-6 shadow-sm">
            <h2 className="text-lg font-semibold">Entrar</h2>
            <p className="mt-1 mb-6 text-sm text-muted-foreground">
              Acesse sua conta para continuar
            </p>

            <form onSubmit={handleSubmit} className="flex flex-col gap-4">
              <div className="flex flex-col gap-1">
                <label htmlFor="email" className="text-sm text-muted-foreground">
                  Email
                </label>
                <input
                  id="email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="rounded-lg border px-3 py-2 text-sm"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label htmlFor="senha" className="text-sm text-muted-foreground">
                  Senha
                </label>
                <input
                  id="senha"
                  type="password"
                  required
                  value={senha}
                  onChange={(e) => setSenha(e.target.value)}
                  className="rounded-lg border px-3 py-2 text-sm"
                />
              </div>
              {erro && <p className="text-sm text-destructive">{erro}</p>}
              <Button type="submit" size="lg" disabled={carregando} className="w-full">
                {carregando ? 'Entrando...' : 'Entrar'}
              </Button>
            </form>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Login
