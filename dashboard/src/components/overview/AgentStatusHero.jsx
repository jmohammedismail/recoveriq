import { useState, useEffect } from 'react'
import { Shield, Sparkles, CheckCircle2, RefreshCw, Activity, ArrowRight, Zap, Eye, Database, Cpu, ChevronDown, ChevronUp } from 'lucide-react'

export default function AgentStatusHero({ activePhase, currentStepIndex, attentionCount = 2, activePayment = 'pay_005' }) {
  const [showStream, setShowStream] = useState(false)
  const [dots, setDots] = useState('')

  useEffect(() => {
    const interval = setInterval(() => {
      setDots(prev => prev.length >= 3 ? '' : prev + '.')
    }, 600)
    return () => clearInterval(interval)
  }, [])

  const stages = [
    { id: 'OBSERVING', label: '1. Telemetry', icon: Eye },
    { id: 'ANALYZING', label: '2. Reconciliation', icon: Database },
    { id: 'DECIDING', label: '3. Policy Gate', icon: Shield },
    { id: 'RECOVERING', label: '4. Recovery Sync', icon: Zap },
    { id: 'VERIFYING', label: '5. Verification', icon: CheckCircle2 }
  ]

  const phaseIndex = activePhase === 'OBSERVING' ? 0
    : activePhase === 'ANALYZING' ? 1
    : activePhase === 'DECIDING' ? 2
    : activePhase === 'RECOVERING' ? 3
    : 4

  const pluralAttention = attentionCount === 1 ? '1 Payment Needs Review' : `${attentionCount} Payments Need Review`

  return (
    <div className="space-y-3">
      
      {/* Merchant-First Reassuring Banner (Clean White & High Trust) */}
      <div className="p-5 bg-white rounded-2xl border border-slate-200 shadow-xs space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
              <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-700">
                RecoverIQ Assistant Active
              </span>
              <span className="text-[10px] font-semibold bg-slate-100 text-slate-600 px-2 py-0.5 rounded border border-slate-200">
                Continuous Protection
              </span>
            </div>
            <h2 className="text-base sm:text-lg font-bold text-slate-900 tracking-tight leading-snug">
              RecoverIQ Assistant — <span className="text-amber-700 font-semibold">{pluralAttention}.</span> Recovery paused on delayed orders to protect against duplicate fulfillment.
            </h2>
          </div>

          <div className="flex items-center gap-2 self-start sm:self-auto flex-shrink-0">
            {attentionCount > 0 ? (
              <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-xs font-bold shadow-2xs">
                <span className="w-2 h-2 rounded-full bg-amber-500"></span>
                <span>{pluralAttention}</span>
              </div>
            ) : (
              <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-bold shadow-2xs">
                <CheckCircle2 size={13} className="text-emerald-600" />
                <span>All Systems Reconciled</span>
              </div>
            )}
          </div>
        </div>

        {/* 5-Stage Autonomous Lifecycle Pipeline Bar */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 pt-1 border-t border-slate-100">
          {stages.map((stage, idx) => {
            const isPassed = idx < phaseIndex
            const isCurrent = idx === phaseIndex
            const StageIcon = stage.icon

            return (
              <div
                key={stage.id}
                className={`p-2.5 rounded-xl border text-xs flex items-center gap-2 transition-all ${
                  isCurrent
                    ? 'bg-brand-50 border-brand-300 text-brand-900 shadow-2xs ring-1 ring-brand-400/30'
                    : isPassed
                    ? 'bg-slate-50 border-slate-200 text-emerald-700'
                    : 'bg-slate-50/50 border-slate-200/60 text-slate-400'
                }`}
              >
                <div className={`w-5 h-5 rounded-md flex items-center justify-center text-[10px] font-bold ${
                  isCurrent ? 'bg-brand-600 text-white animate-pulse' : isPassed ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-200 text-slate-400'
                }`}>
                  {isPassed ? '✓' : <StageIcon size={11} />}
                </div>
                <div className="font-semibold truncate">{stage.label}</div>
              </div>
            )
          })}
        </div>

        {/* Expandable Agent Stream Toggle Button (Layer 2 Progressive Disclosure) */}
        <div className="pt-1 flex items-center justify-between text-xs text-slate-500">
          <span className="text-[11px]">Continuous 4-way reconciliation & idempotent order sync</span>
          <button
            onClick={() => setShowStream(!showStream)}
            className="flex items-center gap-1 text-[11px] font-bold text-brand-600 hover:text-brand-700 transition-colors cursor-pointer"
          >
            <span>{showStream ? 'Hide Agent Execution Stream' : 'View Agent Execution Stream'}</span>
            {showStream ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          </button>
        </div>
      </div>

      {/* COLLAPSED AGENT EXECUTION STREAM (Layer 2) */}
      {showStream && (
        <div className="p-4 bg-slate-900 text-white rounded-2xl border border-slate-800 shadow-sm space-y-3 animate-in fade-in-50 duration-150">
          <div className="flex items-center justify-between text-xs border-b border-slate-800 pb-2">
            <div className="flex items-center gap-2">
              <Cpu size={14} className="text-brand-400" />
              <span className="font-bold uppercase tracking-wider text-slate-300">Live Agent Telemetry Stream</span>
            </div>
            <span className="font-mono text-[10px] text-brand-300 bg-slate-800 px-2 py-0.5 rounded">
              Active Focus: {activePayment}
            </span>
          </div>

          <div className="font-mono text-xs text-slate-300 space-y-1">
            <div className="text-emerald-400">● [TELEMETRY] Incoming payment payload verified for {activePayment} (₹3,100)</div>
            <div className="text-brand-300">● [RECONCILIATION] Gateway: SUCCESS (captured) · Merchant Order: MISSING</div>
            <div className="text-amber-300">● [POLICY_GATE] Autonomous order sync paused: Enqueued for operator review</div>
          </div>
        </div>
      )}

    </div>
  )
}
