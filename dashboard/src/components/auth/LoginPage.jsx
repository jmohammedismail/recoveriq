import { useState } from 'react'
import { Shield, Lock, Zap, CheckCircle2, ArrowRight, AlertCircle, Building2, KeyRound } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'

export default function LoginPage({ onLoginSuccess }) {
  const { login, quickDemoLogin } = useAuth()
  const [email, setEmail] = useState('demo@acmepayments.com')
  const [password, setPassword] = useState('demo1234')
  const [error, setError] = useState(null)
  const [isLoading, setIsLoading] = useState(false)

  const handleFormSubmit = (e) => {
    e.preventDefault()
    setError(null)
    setIsLoading(true)

    setTimeout(() => {
      const res = login(email, password)
      setIsLoading(false)
      if (res.success) {
        if (onLoginSuccess) onLoginSuccess()
      } else {
        setError(res.error)
      }
    }, 300)
  }

  const handleOneClickLogin = () => {
    setEmail('demo@acmepayments.com')
    setPassword('demo1234')
    setError(null)
    setIsLoading(true)

    setTimeout(() => {
      quickDemoLogin()
      setIsLoading(false)
      if (onLoginSuccess) onLoginSuccess()
    }, 200)
  }

  return (
    <div className="min-h-screen bg-[#02042B] text-slate-100 flex flex-col justify-between antialiased selection:bg-[#0C66E4] selection:text-white">
      {/* Top Brand Bar */}
      <header className="px-6 py-5 max-w-7xl w-full mx-auto flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-[#0C66E4] flex items-center justify-center shadow-md">
            <Shield size={18} className="text-white" strokeWidth={2.4} />
          </div>
          <div className="flex items-baseline gap-1.5">
            <span className="text-xl font-bold tracking-tight text-white">
              Recover<span className="text-[#0C66E4]">IQ</span>
            </span>
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider hidden sm:inline">
              Payment Recovery Platform
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-800/80 border border-slate-700/60 text-xs font-medium text-slate-300">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse"></span>
            Secure Demo Environment
          </span>
        </div>
      </header>

      {/* Main Login Card */}
      <main className="flex-1 flex items-center justify-center p-4 sm:p-6">
        <div className="w-full max-w-md">
          
          {/* Card Container */}
          <div className="bg-white text-slate-900 rounded-3xl p-7 sm:p-9 shadow-2xl border border-slate-100 space-y-6">
            
            {/* Header / Titles */}
            <div className="space-y-2 text-center">
              <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-blue-50 text-[#0C66E4] mb-1">
                <Building2 size={24} />
              </div>
              <h1 className="text-2xl font-bold tracking-tight text-slate-900">
                Merchant Sign In
              </h1>
              <p className="text-xs text-[#5E6C84]">
                Access the RecoverIQ Autonomous Recovery Command Center
              </p>
            </div>

            {/* ONE-CLICK DEMO LOGIN BUTTON (Prominent) */}
            <div className="space-y-2">
              <button
                type="button"
                onClick={handleOneClickLogin}
                disabled={isLoading}
                className="w-full py-3 px-4 rounded-xl bg-[#0C66E4] hover:bg-[#0052CC] text-white text-sm font-bold transition-all shadow-md hover:shadow-lg flex items-center justify-center gap-2 cursor-pointer active:scale-[0.99] disabled:opacity-50"
              >
                <Zap size={16} className="text-amber-300 fill-amber-300" />
                <span>⚡ One-Click Demo Login (Acme Payments)</span>
              </button>
              <div className="flex items-center justify-between text-[11px] text-[#5E6C84] px-1">
                <span>MID: merchant_acme_001</span>
                <span className="text-emerald-700 font-semibold">Pre-configured Session</span>
              </div>
            </div>

            {/* Divider */}
            <div className="relative flex items-center justify-center">
              <div className="border-t border-slate-200 w-full"></div>
              <span className="bg-white px-3 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                or sign in with email
              </span>
            </div>

            {/* Error Message */}
            {error && (
              <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs font-medium flex items-start gap-2">
                <AlertCircle size={15} className="text-rose-600 flex-shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            {/* Standard Login Form */}
            <form onSubmit={handleFormSubmit} className="space-y-4">
              <div className="space-y-1.5 text-left">
                <label className="text-xs font-semibold text-slate-700">Merchant Email</label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="demo@acmepayments.com"
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-xs bg-slate-50 focus:bg-white focus:outline-hidden focus:ring-2 focus:ring-[#0C66E4]/20 focus:border-[#0C66E4] text-slate-900 transition-all"
                />
              </div>

              <div className="space-y-1.5 text-left">
                <label className="text-xs font-semibold text-slate-700">Password</label>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-xs bg-slate-50 focus:bg-white focus:outline-hidden focus:ring-2 focus:ring-[#0C66E4]/20 focus:border-[#0C66E4] text-slate-900 transition-all"
                />
              </div>

              <button
                type="submit"
                disabled={isLoading}
                className="w-full py-2.5 px-4 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold transition-all shadow-xs flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
              >
                <span>{isLoading ? 'Signing In...' : 'Sign In to Dashboard'}</span>
                <ArrowRight size={14} />
              </button>
            </form>

            {/* Security Indicators Footer */}
            <div className="pt-2 border-t border-slate-100 flex items-center justify-center gap-4 text-[11px] text-[#5E6C84]">
              <span className="flex items-center gap-1">
                <Lock size={11} className="text-slate-400" />
                256-bit SSL Encrypted
              </span>
              <span>•</span>
              <span className="flex items-center gap-1">
                <CheckCircle2 size={11} className="text-emerald-600" />
                RecoverIQ Sandbox
              </span>
            </div>

          </div>

          {/* Quick Sandbox Help Callout */}
          <div className="mt-4 p-3 bg-slate-900/60 border border-slate-800 rounded-2xl text-center text-xs text-slate-400">
            <span>Demo merchant instance initialized for </span>
            <strong className="text-white">Acme Payments</strong>
            <span className="text-slate-500"> (Demo Environment · No real funds)</span>
          </div>

        </div>
      </main>

      {/* Footer */}
      <footer className="py-4 text-center text-[11px] text-slate-500">
        RecoverIQ Autonomous Post-Payment Recovery & Operator Orchestration · Sandbox Environment
      </footer>
    </div>
  )
}
