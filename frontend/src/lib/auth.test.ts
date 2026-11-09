import { beforeEach, describe, expect, it } from 'vitest'
import { clearToken, getToken, setToken } from './auth'

describe('auth token storage', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('retorna null quando não há token salvo', () => {
    expect(getToken()).toBeNull()
  })

  it('salva e recupera o token', () => {
    setToken('token-de-teste')
    expect(getToken()).toBe('token-de-teste')
  })

  it('limpa o token salvo', () => {
    setToken('token-de-teste')
    clearToken()
    expect(getToken()).toBeNull()
  })
})
