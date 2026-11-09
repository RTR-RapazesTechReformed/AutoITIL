// auth.ts — guarda o JWT emitido por POST /api/auth/login em localStorage.
// Substitui o antigo VITE_API_KEY fixo.

export const AUTH_TOKEN_STORAGE_KEY = 'autoitil-auth-token'

export function getToken(): string | null {
  return localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY)
}
