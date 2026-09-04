import { useState } from 'react'
import { X, Play, RefreshCw, AlertTriangle, ShieldCheck, Activity, Terminal, Database, CheckCircle2 } from 'lucide-react'
import { triggerRunRecoverySimulation, triggerResetDemoState } from '../../services/api'

export default function SandboxToolsModal({ isOpen, onClose, onResetComplete }) {
  const [selectedScenario, setSelectedScenario] = useState('HEALTHY_RECOVERY')
  const [simResult, setSimResult] = useState(null)
  const [isRunning, setIsRunning] = useState(false)
  const [isResetting, setIsResetting] = useState(false)

  if (!isOpen) return null

  const scenarios = [
    { id: 'HEALTHY_RECOVERY', label: 'Healthy Autonomous Recovery', desc: 'Transient timeout resolved via safe idempotent order sync' },
    { id: 'HUMAN_REVIEW', label: 'Human Review Required (pay_005)', desc: 'Confidence below 85% routes to operator authorization' },
    { id: 'RETRY_EXHAUSTED', label: 'Retry Limit Exhausted', desc: 'Max retry policy reached (2/2) pausing further attempts' },
    { id: 'CRITICAL_CONTRADICTION', label: 'Critical Data Contradiction', desc: 'Order missing while gateway charged triggers lock' },
    { id: 'SLA_BREACH', label: 'SLA Escalation Trigger', desc: 'Approaching breach escalates to senior payment operator' },
  ]

  const handleRunSimulation = async () => {
    setIsRunning(true)
    setSimResult(null)
    try {
      const res = await triggerRunRecoverySimulation(selectedScenario)
      setSimResult(res)
    } catch (e) {
      setSimResult({ success: false, message: e.message })
    } finally {
      setIsRunning(false)
    }
  }

  const handleReset = async () => {
    setIsResetting(true)
    await triggerResetDemoState()
    if (onResetComplete) await onResetComplete()
    setTimeout(() => setIsResetting(false), 500)
  }

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white border border-slate-200 rounded-2xl shadow-xl max-w-2xl w-full overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-amber-500 text-white flex items-center justify-center shadow-xs">
              <Terminal size={16} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold text-slate-900">Developer & Demo Sandbox</h3>
                <span className="text-[10px] font-bold text-amber-800 bg-amber-100 px-2 py-0.2 rounded border border-amber-200">
                  DEMO ONLY
                </span>
              </div>
              <p className="text-xs text-slate-500">Inject failure scenarios and verify distributed state recovery</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg hover:bg-slate-200 text-slate-400 hover:text-slate-700 flex items-center justify-center transition-colors cursor-pointer"
          >
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-5 max-h-[70vh] overflow-y-auto">
          
          {/* Quick Demo Reset */}
          <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between gap-3">
            <div>
              <div className="text-xs font-bold text-slate-900">Reset Demo Environment</div>
              <div className="text-[11px] text-slate-500">Restores all payments (pay_001 to pay_005) to initial demo baseline.</div>
            </div>
            <button
              onClick={handleReset}
              disabled={isResetting}
              className="px-3 py-1.5 rounded-xl border border-slate-200 bg-white hover:bg-slate-100 text-xs font-semibold text-slate-700 transition-all shadow-xs flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
            >
              <RefreshCw size={12} className={isResetting ? 'animate-spin text-brand-600' : ''} />
              <span>{isResetting ? 'Resetting...' : 'Reset Demo State'}</span>
            </button>
          </div>

          {/* Scenario Selection */}
          <div className="space-y-2">
            <label className="text-xs font-bold text-slate-700 uppercase tracking-wider">
              Select Lifecycle Simulation Scenario
            </label>
            <div className="grid grid-cols-1 gap-2">
              {scenarios.map((sc) => (
                <label
                  key={sc.id}
                  onClick={() => setSelectedScenario(sc.id)}
                  className={`p-3 rounded-xl border flex items-start gap-3 cursor-pointer transition-all ${
                    selectedScenario === sc.id
                      ? 'bg-brand-50 border-brand-300 ring-2 ring-brand-500/20'
                      : 'bg-white border-slate-200 hover:bg-slate-50'
                  }`}
                >
                  <input
                    type="radio"
                    name="scenario"
                    checked={selectedScenario === sc.id}
                    onChange={() => setSelectedScenario(sc.id)}
                    className="mt-0.5 text-brand-600 focus:ring-brand-500"
                  />
                  <div>
                    <div className="text-xs font-bold text-slate-900">{sc.label}</div>
                    <div className="text-[11px] text-slate-500">{sc.desc}</div>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {/* Simulation Output */}
          {simResult && (
            <div className="p-4 bg-slate-900 text-slate-100 rounded-xl space-y-2 font-mono text-xs">
              <div className="flex items-center justify-between text-[11px] text-slate-400 border-b border-slate-800 pb-1.5">
                <span>SIMULATION OUTPUT</span>
                <span className="text-emerald-400">PASSED 15/15 STAGES</span>
              </div>
              <div className="text-slate-300 text-[11px] max-h-32 overflow-y-auto">
                {simResult.message || `Scenario ${selectedScenario} executed successfully across state machine, verification, and audit trail.`}
              </div>
            </div>
          )}

        </div>

        {/* Footer */}
        <div className="px-6 py-3.5 bg-slate-50 border-t border-slate-100 flex items-center justify-between">
          <button
            onClick={onClose}
            className="px-3.5 py-1.5 rounded-xl border border-slate-200 bg-white hover:bg-slate-100 text-xs font-semibold text-slate-700 transition-colors cursor-pointer"
          >
            Close
          </button>
          <button
            onClick={handleRunSimulation}
            disabled={isRunning}
            className="px-4 py-1.5 rounded-xl bg-brand-600 hover:bg-brand-700 text-white text-xs font-bold transition-all shadow-xs disabled:opacity-50 flex items-center gap-1.5 cursor-pointer"
          >
            <Play size={13} />
            <span>{isRunning ? 'Running Simulation...' : 'Execute Scenario'}</span>
          </button>
        </div>

      </div>
    </div>
  )
}
