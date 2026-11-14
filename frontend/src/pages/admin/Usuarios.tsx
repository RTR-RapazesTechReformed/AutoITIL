import { useEffect, useState, type FormEvent } from 'react'
import { useCurrentUser } from '@/components/RequireAuth'
import { useToast } from '@/lib/toast'
import { createUser, listUsers, updateUser, type AdminUser } from '@/lib/api'

function Usuarios() {
  const usuario = useCurrentUser()
  const { showToast } = useToast()
  const [usuarios, setUsuarios] = useState<AdminUser[]>([])
  const [carregando, setCarregando] = useState(true)
  const [email, setEmail] = useState('')
  const [senha, setSenha] = useState('')
  const [isAdmin, setIsAdmin] = useState(false)

  async function carregar() {
    setCarregando(true)
    try {
      setUsuarios(await listUsers())
    } catch {
      showToast('Falha ao carregar usuários.', 'error')
    } finally {
      setCarregando(false)
    }
  }

  useEffect(() => {
    if (usuario.is_admin) carregar()
  }, [usuario.is_admin])

  async function handleCreate(event: FormEvent) {
    event.preventDefault()
    try {
      await createUser({ email, senha, is_admin: isAdmin })
      setEmail('')
      setSenha('')
      setIsAdmin(false)
      showToast('Usuário criado.')
      await carregar()
    } catch {
      showToast('Falha ao criar usuário.', 'error')
    }
  }

  async function handleToggleAtivo(alvo: AdminUser) {
    try {
      await updateUser(alvo.id, { ativo: !alvo.ativo })
      await carregar()
    } catch {
      showToast('Falha ao atualizar usuário.', 'error')
    }
  }

  if (!usuario.is_admin) {
    return <p className="text-sm text-muted-foreground">Acesso restrito a administradores.</p>
  }

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-lg font-semibold">Usuários</h1>

      <form
        onSubmit={handleCreate}
        className="flex flex-col gap-3 rounded-2xl border bg-card p-4 sm:flex-row sm:flex-wrap sm:items-end"
      >
        <div className="flex flex-col gap-1">
          <label htmlFor="novo-email" className="text-sm text-muted-foreground">
            Email
          </label>
          <input
            id="novo-email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full min-w-0 rounded-lg border px-3 py-2 text-sm sm:w-auto"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="nova-senha" className="text-sm text-muted-foreground">
            Senha
          </label>
          <input
            id="nova-senha"
            type="password"
            required
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
            className="w-full min-w-0 rounded-lg border px-3 py-2 text-sm sm:w-auto"
          />
        </div>
        <label className="flex items-center gap-2 py-1 text-sm">
          <input
            type="checkbox"
            checked={isAdmin}
            onChange={(e) => setIsAdmin(e.target.checked)}
            className="size-4"
          />
          Admin
        </label>
        <button
          type="submit"
          className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
        >
          Criar
        </button>
      </form>

      {carregando ? (
        <p className="text-sm text-muted-foreground">Carregando usuários...</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-muted-foreground">
              <th className="py-2 pr-3">Email</th>
              <th className="py-2 pr-3">Admin</th>
              <th className="py-2 pr-3">Ativo</th>
              <th className="py-2" />
            </tr>
          </thead>
          <tbody>
            {usuarios.map((u) => (
              <tr key={u.id} className="border-t">
                {/* break-all: um email comprido não quebra sozinho (não tem
                    espaço) e empurrava a tabela pra fora da tela no celular. */}
                <td className="py-2 pr-3 break-all">{u.email}</td>
                <td className="py-2 pr-3">{u.is_admin ? 'Sim' : 'Não'}</td>
                <td className="py-2 pr-3">{u.ativo ? 'Sim' : 'Não'}</td>
                <td className="py-2 text-right whitespace-nowrap">
                  <button
                    onClick={() => handleToggleAtivo(u)}
                    className="py-2 text-sm underline"
                  >
                    {u.ativo ? 'Desativar' : 'Ativar'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

export default Usuarios
