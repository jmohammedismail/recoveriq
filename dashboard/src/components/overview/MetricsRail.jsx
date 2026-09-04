import { useEffect, useRef, useState } from 'react'
import { AlertCircle, CheckCircle2, ShieldAlert, Percent, ArrowUpRight, ChevronRight, HelpCircle } from 'lucide-react'
import { metrics as defaultMetrics } from '../../data/metrics'

function useCountUp(target, duration = 600) {
  const [value, setValue] = useState(target || 0)
  const frameRef = useRef(null)

  useEffect(() => {
    if (target === undefined || target === null) return
    const start = performance.now()
    const initialVal = value
    const animate = (now) => {
      const progress = Math.min((now - start) / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3)
      setValue(Math.round(initialVal + eased * (target - initialVal)))
      if (progress < 1) frameRef.current = requestAnimationFrame(animate)
    }
    frameRef.current = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(frameRef.current)
  }, [target, duration])

  return value
}

export default function MetricsRail({ dynamicMetrics, onNavigateToPayments }) {
  const m = dynamicMetrics || defaultMetrics
  const atRisk = useCountUp(m.revenueAtRisk !== undefined ? m.revenueAtRisk : 31600)
  const recovered = useCountUp(m.revenueRecovered !== undefined ? m.revenueRecovered : 5600)
  const needAttention = m.pendingReviewCount !== undefined ? m.pendingReviewCount : 2
  const successRate = m.recoverySuccessRate !== undefined ? m.recoverySuccessRate : (m.recoveryRate || 85)

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      
      {/* 1. Money at Risk */}
      <div
        onClick={() => onNavigateToPayments && onNavigateToPayments('ALL')}
        className="p-4 bg-white hover:bg-slate-50/80 border border-slate-200 rounded-2xl shadow-xs space-y-2 transition-all cursor-pointer group"
      >
        <div className="flex items-center justify-between text-slate-500">
          <div className="flex items-center gap-1.5" title="Total captured revenue across unresolved failed payment attempts requiring recovery or review.">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-600">Money at Risk</span>
            <HelpCircle size={11} className="text-slate-400" />
          </div>
          <div className="w-7 h-7 rounded-lg bg-rose-50 border border-rose-100 flex items-center justify-center text-rose-600 group-hover:scale-105 transition-transform">
            <AlertCircle size={14} />
          </div>
        </div>
        <div className="text-2xl font-bold tracking-tight text-slate-900 font-mono">
          ₹{atRisk.toLocaleString('en-IN')}
        </div>
        <div className="flex items-center justify-between text-[11px] text-slate-500 font-medium">
          <span>Unresolved captured payments</span>
          <ChevronRight size={13} className="text-slate-400 group-hover:text-brand-600 transition-colors" />
        </div>
      </div>

      {/* 2. Money Recovered */}
      <div
        onClick={() => onNavigateToPayments && onNavigateToPayments('RECOVERED')}
        className="p-4 bg-white hover:bg-emerald-50/20 border border-slate-200 hover:border-emerald-200 rounded-2xl shadow-xs space-y-2 transition-all cursor-pointer group"
      >
        <div className="flex items-center justify-between text-slate-500">
          <div className="flex items-center gap-1.5" title="Total revenue successfully synchronized and verified in merchant backend without duplicate customer charges.">
            <span className="text-xs font-bold uppercase tracking-wider text-emerald-800">Money Recovered</span>
            <HelpCircle size={11} className="text-emerald-500" />
          </div>
          <div className="w-7 h-7 rounded-lg bg-emerald-50 border border-emerald-100 flex items-center justify-center text-emerald-600 group-hover:scale-105 transition-transform">
            <CheckCircle2 size={14} />
          </div>
        </div>
        <div className="text-2xl font-bold tracking-tight text-emerald-700 font-mono flex items-baseline gap-1.5">
          <span>₹{recovered.toLocaleString('en-IN')}</span>
          <span className="text-[11px] text-emerald-600 font-semibold flex items-center">
            <ArrowUpRight size={12} /> Live
          </span>
        </div>
        <div className="flex items-center justify-between text-[11px] text-emerald-700 font-medium">
          <span>Recovered without duplicate charges</span>
          <ChevronRight size={13} className="text-emerald-500 group-hover:text-emerald-700 transition-colors" />
        </div>
      </div>

      {/* 3. Needs Attention */}
      <div
        onClick={() => onNavigateToPayments && onNavigateToPayments('NEEDS_ATTENTION')}
        className="p-4 bg-white hover:bg-amber-50/30 border border-slate-200 hover:border-amber-200 rounded-2xl shadow-xs space-y-2 transition-all cursor-pointer group"
      >
        <div className="flex items-center justify-between text-slate-500">
          <div className="flex items-center gap-1.5" title="Payments where AI confidence was sub-85% or order creation was delayed, routed to Human Review queue.">
            <span className="text-xs font-bold uppercase tracking-wider text-amber-800">Needs Attention</span>
            <HelpCircle size={11} className="text-amber-600" />
          </div>
          <div className="w-7 h-7 rounded-lg bg-amber-50 border border-amber-100 flex items-center justify-center text-amber-600 group-hover:scale-105 transition-transform">
            <ShieldAlert size={14} />
          </div>
        </div>
        <div className="text-2xl font-bold tracking-tight text-amber-800 font-mono">
          {needAttention}
        </div>
        <div className="flex items-center justify-between text-[11px] text-amber-800 font-medium">
          <span>Awaiting merchant review</span>
          <ChevronRight size={13} className="text-amber-500 group-hover:text-amber-700 transition-colors" />
        </div>
      </div>

      {/* 4. Recovery Success Rate */}
      <div
        onClick={() => onNavigateToPayments && onNavigateToPayments('ALL')}
        className="p-4 bg-white hover:bg-slate-50/80 border border-slate-200 rounded-2xl shadow-xs space-y-2 transition-all cursor-pointer group"
      >
        <div className="flex items-center justify-between text-slate-500">
          <div className="flex items-center gap-1.5" title="Percentage of actionable failed payments successfully reconciled and verified in database.">
            <span className="text-xs font-bold uppercase tracking-wider text-brand-800">Recovery Rate</span>
            <HelpCircle size={11} className="text-brand-500" />
          </div>
          <div className="w-7 h-7 rounded-lg bg-brand-50 border border-brand-100 flex items-center justify-center text-brand-600 group-hover:scale-105 transition-transform">
            <Percent size={14} />
          </div>
        </div>
        <div className="text-2xl font-bold tracking-tight text-slate-900 font-mono">
          {successRate}%
        </div>
        <div className="flex items-center justify-between text-[11px] text-slate-500 font-medium">
          <span>Automated & approved success rate</span>
          <ChevronRight size={13} className="text-slate-400 group-hover:text-brand-600 transition-colors" />
        </div>
      </div>

    </div>
  )
}
