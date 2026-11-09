import { createContext, useContext, useEffect, useState } from 'react'
import { Navigate, Outlet } from 'react-router-dom'
import { getCurrentUser, type CurrentUser } from '@/lib/api'
import { clearToken, getToken } from '@/lib/auth'

const CurrentUserContext = createContext<CurrentUser | null>(null)

/** Usuário logado — só pode ser usado dentro de uma rota protegida por
 * RequireAuth (é ele quem provê o contexto). */
export function useCurrentUser(): CurrentUser {
  const usuario = useContext(CurrentUserContext)
  if (!usuario) {
    throw new Error(
      'useCurrentUser precisa ser usado dentro de uma rota protegida por RequireAuth.',
    )
  }
  return usuario
}

type Status = 'checking' | 'ok' | 'unauthenticated'

function RequireAuth() {
  const [usuario, setUsuario] = useState<CurrentUser | null>(null)
  const [status, setStatus] = useState<Status>(getToken() ? 'checking' : 'unauthenticated')

  useEffect(() => {
    if (!getToken()) return
    getCurrentUser()
      .then((user) => {
        setUsuario(user)
        setStatus('ok')
      })
      .catch(() => {
        clearToken()
        setStatus('unauthenticated')
      })
  }, [])

  if (status === 'unauthenticated') return <Navigate to="/login" replace />
  if (status === 'checking' || !usuario) return null

  return (
    <CurrentUserContext.Provider value={usuario}>
      <Outlet />
    </CurrentUserContext.Provider>
  )
}

export default RequireAuth
