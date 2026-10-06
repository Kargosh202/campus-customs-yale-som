import { useEffect, useState, type ReactNode } from 'react'
import { AuthContext, postJson, type AuthContextValue, type User } from '../auth'

export default function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/auth/me')
      .then((res) => (res.ok ? res.json() : null))
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false))
  }, [])

  const value: AuthContextValue = {
    user,
    loading,
    login: async (email, password) => setUser(await postJson('/api/auth/login', { email, password })),
    register: async (input) => setUser(await postJson('/api/auth/register', input)),
    logout: async () => {
      await fetch('/api/auth/logout', { method: 'POST' })
      setUser(null)
    },
  }
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
