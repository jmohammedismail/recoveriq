import { useState, useEffect } from 'react'
import { Shield, RefreshCw, Terminal, CheckCircle2, AlertCircle, HelpCircle, User, LogOut, ChevronDown } from 'lucide-react'
import { checkAgentHealth, triggerResetDemoState } from '../../services/api'
import { useAuth } from '../../context/AuthContext'
import SandboxToolsModal from './SandboxToolsModal'
import HelpCenterModal from '../help/HelpCenterModal'

// Streamlined 4-tab primary navigation (File Analysis is embedded in Payments)
const tabs = ['Overview', 'Payments', 'File Analysis', 'Activity', 'Audit']

export default function TopNav({ activeTab, onTabChange, onDataRefresh, incidentsList = [] }) {
  const { merchant, logout } = useAuth()
  const [backendOnline, setBackendOnline] = useState(false)
  const [isProcessing, setIsProcessing] = useState(false)
  const [showSandboxModal, setShowSandboxModal] = useState(false)
  const [showHelpModal, setShowHelpModal] = useState(false)
  const [showUserMenu, setShowUserMenu] = useState(false)

  useEffect(() => {
    async function check() {
      const health = await checkAgentHealth()
      setBackendOnline(health.status === 'ONLINE')
    }
    check()
    const interval = setInterval(check, 5000)
    return () => clearInterval(interval)
  }, [])

  const handleResetDemo = async () => {
    setIsProcessing(true)
    await triggerResetDemoState()
    if (onDataRefresh) await onDataRefresh()
    setTimeout(() => setIsProcessing(false), 500)
  }

  return (
    <header className="sticky top-0 z-40 w-full bg-white border-b border-slate-200 shadow-xs">
      <div className="max-w-[1600px] mx-auto px-4 sm:px-6 h-14 flex items-center justify-between gap-4">
        
        {/* LEFT: Brand Identity */}
        <div className="flex items-center gap-2.5 flex-shrink-0">
          <div className="w-7 h-7 rounded-lg bg-brand-600 flex items-center justify-center shadow-xs">
            <Shield size={16} className="text-white" strokeWidth={2.2} />
          </div>
          <div className="flex items-baseline gap-1.5">
            <span className="text-base font-bold tracking-tight text-slate-900 leading-none">
              Recover<span className="text-brand-600">IQ</span>
            </span>
            <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider hidden sm:inline">
              Payment Recovery
            </span>
          </div>
        </div>

        {/* CENTER: Navigation Tabs (Overview, Payments, Activity, Audit) */}
        <nav className="flex items-center gap-1 bg-slate-100 p-1 rounded-xl border border-slate-200 overflow-x-auto">
          {tabs.map((tab) => {
            const isActive = activeTab === tab
            return (
              <button
                key={tab}
                onClick={() => onTabChange(tab)}
                className={`px-3.5 py-1 rounded-lg text-xs font-semibold transition-all cursor-pointer whitespace-nowrap ${
                  isActive
                    ? 'bg-white text-brand-700 shadow-xs'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/60'
                }`}
              >
                {tab}
              </button>
            )
          })}
        </nav>

        {/* RIGHT: Consolidated Status, Controls & Merchant Identity */}
        <div className="flex items-center gap-2 flex-shrink-0">
          
          {/* How it Works / Help Guide Button */}
          <button
            onClick={() => setShowHelpModal(true)}
            title="How to Use RecoverIQ — Product Guide"
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-brand-200 bg-brand-50 hover:bg-brand-100 text-xs font-bold text-brand-700 transition-colors shadow-2xs cursor-pointer"
          >
            <HelpCircle size={13} className="text-brand-600" />
            <span className="hidden md:inline">How it works</span>
          </button>

          {/* Consolidated Environment Pill: [ 🟡 SANDBOX ] */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-amber-50 border border-amber-200 text-[11px] font-bold text-amber-800">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse"></span>
            <span>SANDBOX</span>
          </div>

          {/* Live Indicator: [ 🟢 Pipeline Active ] */}
          <div className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-emerald-50 border border-emerald-200 text-[11px] font-semibold text-emerald-800">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
            <span>Pipeline Active</span>
          </div>

          {/* Action Control: [ Demo Tools ▾ ] */}
          <button
            onClick={() => setShowSandboxModal(true)}
            title="Open Developer & Demo Sandbox Tools"
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-slate-200 bg-slate-50 hover:bg-slate-100 text-xs font-semibold text-slate-700 transition-colors shadow-2xs cursor-pointer"
          >
            <Terminal size={12} className="text-amber-600" />
            <span className="hidden sm:inline">Demo Tools</span>
          </button>

          {/* Action Control: [ Reset ] */}
          <button
            onClick={handleResetDemo}
            disabled={isProcessing}
            title="Reset database to initial baseline"
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 text-xs font-semibold text-slate-700 transition-colors shadow-xs disabled:opacity-50 cursor-pointer"
          >
            <RefreshCw size={11} className={isProcessing ? 'animate-spin text-brand-600' : 'text-slate-400'} />
            <span className="hidden sm:inline">Reset</span>
          </button>

          {/* Merchant Profile & Logout Menu */}
          <div className="relative">
            <button
              onClick={() => setShowUserMenu(!showUserMenu)}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-slate-200 bg-slate-50 hover:bg-slate-100 text-xs font-semibold text-slate-700 transition-colors cursor-pointer"
            >
              <User size={12} className="text-brand-600" />
              <span className="hidden xl:inline">{merchant?.name || 'Acme Payments'}</span>
              <ChevronDown size={11} className="text-slate-400" />
            </button>

            {showUserMenu && (
              <div className="absolute right-0 mt-1.5 w-56 bg-white border border-slate-200 rounded-xl shadow-lg p-2 z-50 text-xs space-y-1">
                <div className="px-2.5 py-2 border-b border-slate-100 space-y-0.5">
                  <div className="font-bold text-slate-900">{merchant?.name || 'Acme Payments'}</div>
                  <div className="text-[11px] text-slate-500 font-mono">MID: {merchant?.id || 'merchant_acme_001'}</div>
                  <div className="text-[10px] text-emerald-700 font-semibold">{merchant?.email || 'demo@acmepayments.com'}</div>
                </div>
                <button
                  onClick={() => {
                    setShowUserMenu(false)
                    logout()
                  }}
                  className="w-full px-2.5 py-1.5 rounded-lg text-rose-700 hover:bg-rose-50 font-semibold flex items-center gap-2 cursor-pointer transition-colors"
                >
                  <LogOut size={13} />
                  <span>Sign Out</span>
                </button>
              </div>
            )}
          </div>

        </div>

      </div>

      {/* Developer / Demo Sandbox Modal */}
      <SandboxToolsModal
        isOpen={showSandboxModal}
        onClose={() => setShowSandboxModal(false)}
        onResetComplete={onDataRefresh}
      />

      {/* Product Guide & Help Modal */}
      <HelpCenterModal
        isOpen={showHelpModal}
        onClose={() => setShowHelpModal(false)}
        demoIncidents={incidentsList}
      />
    </header>
  )
}
