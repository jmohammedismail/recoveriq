import { createContext, useContext, useState, useEffect } from 'react'
import merchantsData from '../data/merchants.json'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [merchant, setMerchant] = useState(() => {
    try {
      const stored = localStorage.getItem('recoveriq_merchant_session')
      return stored ? JSON.parse(stored) : null
    } catch {
      return null
    }
  })

  const login = (email, password) => {
    const cleanEmail = (email || '').trim().toLowerCase()
    const cleanPassword = (password || '').trim()

    const user = merchantsData.find(
      (m) => m.email.toLowerCase() === cleanEmail && m.password === cleanPassword
    )

    if (user) {
      const sessionUser = {
        id: user.id,
        name: user.name,
        email: user.email,
        role: user.role,
        environment: user.environment,
        currency: user.currency,
        token: `demo_jwt_${user.id}_${Date.now()}`
      }
      setMerchant(sessionUser)
      localStorage.setItem('recoveriq_merchant_session', JSON.stringify(sessionUser))
      return { success: true, user: sessionUser }
    } else {
      return { success: false, error: 'Invalid merchant email or password. Use demo@acmepayments.com / demo1234.' }
    }
  }

  const quickDemoLogin = () => {
    const demoUser = merchantsData[0]
    const sessionUser = {
      id: demoUser.id,
      name: demoUser.name,
      email: demoUser.email,
      role: demoUser.role,
      environment: demoUser.environment,
      currency: demoUser.currency,
      token: `demo_jwt_${demoUser.id}_${Date.now()}`
    }
    setMerchant(sessionUser)
    localStorage.setItem('recoveriq_merchant_session', JSON.stringify(sessionUser))
    return sessionUser
  }

  const logout = () => {
    setMerchant(null)
    localStorage.removeItem('recoveriq_merchant_session')
  }

  return (
    <AuthContext.Provider
      value={{
        merchant,
        isAuthenticated: !!merchant,
        login,
        quickDemoLogin,
        logout
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
