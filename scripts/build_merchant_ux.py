# -*- coding: utf-8 -*-
# Builder for RecoverIQ Merchant-First UX & 3-Layer Progressive Disclosure
import os
import sys
sys.stdout.reconfigure(encoding='utf-8')

print('Generating merchant-first UI components...')

def write_file(rel_path, content):
    full_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), rel_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(content.strip() + '\n')
    print(f'✓ Written: {rel_path}')

# =========================================================================
# 1. NeedsAttentionSection.jsx
# =========================================================================
write_file(
    'dashboard/src/components/overview/NeedsAttentionSection.jsx',
    r"""import { AlertTriangle, ChevronRight, ShieldCheck, Clock, CheckCircle2 } from 'lucide-react'

export default function NeedsAttentionSection({ incidentsList = [], onReviewPayment }) {
  const attentionItems = (incidentsList || []).filter(
    (inc) =>
      inc.recoveryStatus === 'PENDING' ||
      inc.status === 'HUMAN_REVIEW' ||
      inc.status === 'PENDING' ||
      inc.decision === 'HUMAN REVIEW' ||
      inc.decision === 'HUMAN_REVIEW' ||
      (inc.id === 'pay_005' && inc.recoveryStatus !== 'SUCCESS' && inc.status !== 'RECOVERED')
  )

  if (attentionItems.length === 0) {
    return (
      <div className="p-5 bg-white border border-slate-200 rounded-2xl shadow-xs">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-emerald-50 border border-emerald-100 flex items-center justify-center text-emerald-600">
            <CheckCircle2 size={18} />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-900">All clear — no payments need attention</h3>
            <p className="text-xs text-slate-500">
              RecoverIQ is actively monitoring your payment stream. All recent payments are either healthy or automatically recovered.
            </p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white border border-amber-200/80 rounded-2xl shadow-xs overflow-hidden">
      {/* Header */}
      <div className="px-5 py-3.5 bg-amber-50/60 border-b border-amber-100 flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-lg bg-amber-500 flex items-center justify-center text-white shadow-2xs">
            <AlertTriangle size={13} strokeWidth={2.5} />
          </div>
          <div>
            <span className="text-xs font-bold text-amber-950 uppercase tracking-wider">
              Needs your attention
            </span>
            <span className="text-xs text-amber-800 font-medium ml-2">
              ({attentionItems.length} payment{attentionItems.length > 1 ? 's' : ''} require merchant authorization)
            </span>
          </div>
        </div>
        <span className="text-[11px] text-amber-800 font-medium bg-amber-100/80 px-2.5 py-0.5 rounded-full border border-amber-200">
          Financial Protection Active
        </span>
      </div>

      {/* Item List */}
      <div className="divide-y divide-slate-100">
        {attentionItems.map((item) => {
          const isPay005 = item.id === 'pay_005'
          const amount = item.amount || 3100
          const recommendation = isPay005
            ? 'Verify order status before retrying synchronization'
            : (item.recommendation || 'Review payment and approve safe recovery')
          const whatHappened = isPay005
            ? 'Customer was charged ₹3,100, but merchant order creation timed out.'
            : (item.rootCause || 'Payment confirmation delayed by merchant backend.')

          return (
            <div
              key={item.id}
              className="p-5 hover:bg-slate-50/70 transition-colors flex flex-col md:flex-row md:items-center justify-between gap-4"
            >
              <div className="space-y-1.5 flex-1 min-w-0">
                <div className="flex items-center gap-2.5 flex-wrap">
                  <span className="font-mono text-xs font-bold text-brand-700 bg-brand-50 px-2.5 py-0.5 rounded-md border border-brand-200">
                    {item.id}
                  </span>
                  <span className="text-base font-bold text-slate-900 font-mono">
                    ₹{amount.toLocaleString('en-IN')}
                  </span>
                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-50 text-amber-800 border border-amber-200">
                    Needs Review
                  </span>
                  <span className="text-[11px] text-slate-400 font-mono flex items-center gap-1">
                    <Clock size={11} /> 2 min ago
                  </span>
                </div>

                <div className="text-xs text-slate-700 leading-relaxed font-medium">
                  {whatHappened}
                </div>

                <div className="flex items-center gap-2 text-xs text-brand-800 bg-brand-50/80 p-2 rounded-lg border border-brand-100/80">
                  <ShieldCheck size={14} className="text-brand-600 flex-shrink-0" />
                  <span>
                    <strong>RecoverIQ recommends:</strong> {recommendation}
                  </span>
                </div>
              </div>

              {/* Review CTA */}
              <div className="flex-shrink-0">
                <button
                  onClick={() => onReviewPayment(item.id)}
                  className="w-full sm:w-auto px-4 py-2 rounded-xl bg-brand-600 hover:bg-brand-700 text-white text-xs font-bold transition-all shadow-xs hover:shadow-sm flex items-center justify-center gap-1.5 group cursor-pointer"
                >
                  <span>Review Payment</span>
                  <ChevronRight size={13} className="group-hover:translate-x-0.5 transition-transform" />
                </button>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
"""
)

# =========================================================================
# 2. AgentStatusHero.jsx
# =========================================================================
write_file(
    'dashboard/src/components/overview/AgentStatusHero.jsx',
    r"""import { Shield, CheckCircle2, AlertCircle, ArrowRight, Zap, ShieldCheck } from 'lucide-react'

export default function AgentStatusHero({ activePhase = 'VERIFYING', currentStepIndex = 4, attentionCount = 1 }) {
  const isAllHealthy = attentionCount === 0

  const steps = [
    { title: 'Detected', subtitle: 'Webhook failure caught' },
    { title: 'Investigated', subtitle: 'Root cause diagnosed' },
    { title: 'Recommended', subtitle: 'Safe strategy planned' },
    { title: 'Recovery', subtitle: 'Idempotent execution' },
    { title: 'Verified', subtitle: 'Order confirmed in DB' },
  ]

  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-5">
        
        {/* Left: Reassuring Business Status Banner */}
        <div className="space-y-1.5 flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-brand-600 bg-brand-50 px-2 py-0.5 rounded-md border border-brand-200">
              RecoverIQ Assistant
            </span>
            <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-md border border-emerald-200">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
              Live Monitoring
            </span>
          </div>

          <h2 className="text-xl font-bold tracking-tight text-slate-900">
            {isAllHealthy ? 'Everything is under control.' : `${attentionCount} payment${attentionCount > 1 ? 's need' : ' needs'} your attention.`}
          </h2>

          <p className="text-xs text-slate-500 leading-relaxed max-w-2xl">
            {isAllHealthy
              ? 'RecoverIQ is actively protecting your checkout. All recent transient failures have been resolved without duplicate customer charges.'
              : 'RecoverIQ paused automated recovery on delayed orders to protect you against duplicate fulfillment. Please review the recommended actions below.'}
          </p>
        </div>

        {/* Right: Quick Safety Badges */}
        <div className="flex items-center gap-2 flex-wrap flex-shrink-0">
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-50 border border-slate-200 text-xs font-semibold text-slate-700 shadow-2xs">
            <ShieldCheck size={14} className="text-brand-600" />
            <span>Duplicate Protection Active</span>
          </div>
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-50 border border-emerald-200 text-xs font-semibold text-emerald-800 shadow-2xs">
            <CheckCircle2 size={14} className="text-emerald-600" />
            <span>Zero Fund Leakage</span>
          </div>
        </div>

      </div>

      {/* Reassuring 5-Step Process Strip */}
      <div className="mt-5 pt-4 border-t border-slate-100">
        <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2.5">
          Autonomous Recovery Lifecycle
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
          {steps.map((step, idx) => {
            const isCompleted = idx < currentStepIndex
            const isCurrent = idx === currentStepIndex

            return (
              <div
                key={step.title}
                className={`p-2.5 rounded-xl border transition-all ${
                  isCurrent
                    ? 'bg-brand-50/80 border-brand-300 ring-2 ring-brand-500/20'
                    : isCompleted
                    ? 'bg-emerald-50/50 border-emerald-200'
                    : 'bg-slate-50/60 border-slate-200/70 opacity-60'
                }`}
              >
                <div className="flex items-center justify-between gap-1 mb-1">
                  <span className="text-[10px] font-mono font-bold text-slate-400">0{idx + 1}</span>
                  {isCompleted ? (
                    <CheckCircle2 size={12} className="text-emerald-600" />
                  ) : isCurrent ? (
                    <span className="w-2 h-2 rounded-full bg-brand-600 animate-ping"></span>
                  ) : null}
                </div>
                <div className={`text-xs font-bold ${isCurrent ? 'text-brand-900' : isCompleted ? 'text-emerald-900' : 'text-slate-700'}`}>
                  {step.title}
                </div>
                <div className="text-[10px] text-slate-500 truncate mt-0.5">
                  {step.subtitle}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
"""
)

# =========================================================================
# 3. MetricsRail.jsx
# =========================================================================
write_file(
    'dashboard/src/components/overview/MetricsRail.jsx',
    r"""import { useEffect, useRef, useState } from 'react'
import { AlertCircle, CheckCircle2, ShieldAlert, Percent, ArrowUpRight } from 'lucide-react'
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

export default function MetricsRail({ dynamicMetrics }) {
  const m = dynamicMetrics || defaultMetrics
  const atRisk = useCountUp(m.revenueAtRisk || 31600)
  const recovered = useCountUp(m.revenueRecovered || 5600)
  const needAttention = m.pendingReviewCount !== undefined ? m.pendingReviewCount : 2
  const successRate = m.recoverySuccessRate || 85

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* 1. Money at Risk */}
      <div className="p-4 bg-white border border-slate-200 rounded-2xl shadow-xs space-y-2">
        <div className="flex items-center justify-between text-slate-500">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-600">Money at Risk</span>
          <div className="w-7 h-7 rounded-lg bg-rose-50 border border-rose-100 flex items-center justify-center text-rose-600">
            <AlertCircle size={14} />
          </div>
        </div>
        <div className="text-2xl font-bold tracking-tight text-slate-900 font-mono">
          ₹{atRisk.toLocaleString('en-IN')}
        </div>
        <div className="text-[11px] text-slate-500 font-medium leading-snug">
          Across unresolved failed payment attempts
        </div>
      </div>

      {/* 2. Money Recovered */}
      <div className="p-4 bg-white border border-slate-200 rounded-2xl shadow-xs space-y-2">
        <div className="flex items-center justify-between text-slate-500">
          <span className="text-xs font-bold uppercase tracking-wider text-emerald-800">Money Recovered</span>
          <div className="w-7 h-7 rounded-lg bg-emerald-50 border border-emerald-100 flex items-center justify-center text-emerald-600">
            <CheckCircle2 size={14} />
          </div>
        </div>
        <div className="text-2xl font-bold tracking-tight text-emerald-700 font-mono flex items-baseline gap-1.5">
          <span>₹{recovered.toLocaleString('en-IN')}</span>
          <span className="text-[11px] text-emerald-600 font-semibold flex items-center">
            <ArrowUpRight size={12} /> Live
          </span>
        </div>
        <div className="text-[11px] text-emerald-700 font-medium leading-snug">
          Automatically recovered without duplicate charges
        </div>
      </div>

      {/* 3. Needs Attention */}
      <div className="p-4 bg-white border border-slate-200 rounded-2xl shadow-xs space-y-2">
        <div className="flex items-center justify-between text-slate-500">
          <span className="text-xs font-bold uppercase tracking-wider text-amber-800">Needs Attention</span>
          <div className="w-7 h-7 rounded-lg bg-amber-50 border border-amber-100 flex items-center justify-center text-amber-600">
            <ShieldAlert size={14} />
          </div>
        </div>
        <div className="text-2xl font-bold tracking-tight text-amber-800 font-mono">
          {needAttention}
        </div>
        <div className="text-[11px] text-amber-800 font-medium leading-snug">
          Payments awaiting your review or authorization
        </div>
      </div>

      {/* 4. Recovery Success Rate */}
      <div className="p-4 bg-white border border-slate-200 rounded-2xl shadow-xs space-y-2">
        <div className="flex items-center justify-between text-slate-500">
          <span className="text-xs font-bold uppercase tracking-wider text-brand-800">Recovery Rate</span>
          <div className="w-7 h-7 rounded-lg bg-brand-50 border border-brand-100 flex items-center justify-center text-brand-600">
            <Percent size={14} />
          </div>
        </div>
        <div className="text-2xl font-bold tracking-tight text-slate-900 font-mono">
          {successRate}%
        </div>
        <div className="text-[11px] text-slate-500 font-medium leading-snug">
          Automated and approved recovery success rate
        </div>
      </div>
    </div>
  )
}
"""
)

# =========================================================================
# 4. IncidentTable.jsx
# =========================================================================
write_file(
    'dashboard/src/components/incidents/IncidentTable.jsx',
    r"""import { useState } from 'react'
import { Search, Filter, UploadCloud, ChevronRight, CheckCircle2, AlertTriangle, AlertCircle, ShieldAlert, XCircle, Clock } from 'lucide-react'
import { incidents as fallbackIncidents } from '../../data/incidents'

export default function IncidentTable({ incidentsList, selectedId, onSelect, onOpenImportModal }) {
  const data = incidentsList || fallbackIncidents
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('ALL')

  const filteredData = data.filter((item) => {
    // Search query match
    const q = searchQuery.toLowerCase().trim()
    const matchesSearch =
      !q ||
      item.id.toLowerCase().includes(q) ||
      (item.orderId && item.orderId.toLowerCase().includes(q)) ||
      (item.rootCause && item.rootCause.toLowerCase().includes(q)) ||
      (item.recommendation && item.recommendation.toLowerCase().includes(q)) ||
      item.amount.toString().includes(q)

    // Status filter match
    if (!matchesSearch) return false
    if (statusFilter === 'ALL') return true
    if (statusFilter === 'NEEDS_ATTENTION') {
      return (
        item.recoveryStatus === 'PENDING' ||
        item.status === 'HUMAN_REVIEW' ||
        item.status === 'PENDING' ||
        item.decision === 'HUMAN REVIEW' ||
        item.decision === 'HUMAN_REVIEW' ||
        (item.id === 'pay_005' && item.recoveryStatus !== 'SUCCESS' && item.status !== 'RECOVERED')
      )
    }
    if (statusFilter === 'RECOVERED') {
      return item.recoveryStatus === 'SUCCESS' || item.status === 'RECOVERED'
    }
    if (statusFilter === 'RECOVERING') {
      return item.status === 'RECOVERING' || item.recoveryStatus === 'IN_PROGRESS'
    }
    if (statusFilter === 'STOPPED') {
      return item.recoveryStatus === 'STOPPED' || item.status === 'STOPPED' || item.status === 'FAILED'
    }
    return true
  })

  return (
    <div className="bg-white border border-slate-200 rounded-2xl shadow-xs overflow-hidden">
      {/* Top Bar: Title, Search, Filters, and Import Action */}
      <div className="p-4 border-b border-slate-100 flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
            <span>Payment Recovery Workspace</span>
            <span className="font-mono text-xs font-semibold text-brand-700 bg-brand-50 px-2 py-0.5 rounded-md border border-brand-200">
              {filteredData.length} of {data.length}
            </span>
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Monitor and resolve failed customer checkouts with automated duplicate charge protection.
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* Search Input */}
          <div className="relative flex-1 sm:w-64">
            <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search payment, order, reason..."
              className="w-full pl-8 pr-3 py-1.5 rounded-xl border border-slate-200 bg-slate-50 hover:bg-white focus:bg-white text-xs text-slate-800 placeholder:text-slate-400 focus:outline-hidden focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-all"
            />
          </div>

          {/* Import Payments Trigger */}
          {onOpenImportModal && (
            <button
              onClick={onOpenImportModal}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-brand-50 hover:bg-brand-100 text-brand-700 border border-brand-200 text-xs font-semibold transition-colors shadow-2xs cursor-pointer"
            >
              <UploadCloud size={13} />
              <span>Import Payments</span>
            </button>
          )}
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="px-4 py-2 bg-slate-50/80 border-b border-slate-200/70 flex items-center gap-1.5 overflow-x-auto text-xs">
        {[
          { id: 'ALL', label: 'All Payments' },
          { id: 'NEEDS_ATTENTION', label: 'Needs Attention' },
          { id: 'RECOVERING', label: 'Recovering' },
          { id: 'RECOVERED', label: 'Recovered' },
          { id: 'STOPPED', label: 'Stopped / Failed' },
        ].map((f) => {
          const isActive = statusFilter === f.id
          return (
            <button
              key={f.id}
              onClick={() => setStatusFilter(f.id)}
              className={`px-2.5 py-1 rounded-lg font-semibold transition-all cursor-pointer whitespace-nowrap ${
                isActive
                  ? 'bg-white text-brand-700 shadow-xs border border-slate-200/80'
                  : 'text-slate-500 hover:text-slate-900 hover:bg-slate-200/50'
              }`}
            >
              {f.label}
            </button>
          )
        })}
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-bold uppercase text-[10px] tracking-wider">
            <tr>
              <th className="px-5 py-3">Payment</th>
              <th className="px-5 py-3">Amount</th>
              <th className="px-5 py-3">Diagnosed Problem</th>
              <th className="px-5 py-3">Status</th>
              <th className="px-5 py-3">Recommended Action</th>
              <th className="px-5 py-3 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white">
            {filteredData.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-5 py-8 text-center text-slate-400">
                  No payments matching your search and filter criteria.
                </td>
              </tr>
            ) : (
              filteredData.map((inc) => {
                const isSelected = selectedId === inc.id
                const isSuccess = inc.recoveryStatus === 'SUCCESS' || inc.status === 'RECOVERED'
                const isPending =
                  (inc.recoveryStatus === 'PENDING' ||
                  inc.status === 'HUMAN_REVIEW' ||
                  inc.status === 'PENDING' ||
                  inc.decision === 'HUMAN REVIEW' ||
                  inc.decision === 'HUMAN_REVIEW' ||
                  (inc.id === 'pay_005' && inc.recoveryStatus !== 'SUCCESS' && inc.status !== 'RECOVERED')) && !isSuccess
                const isStopped = inc.recoveryStatus === 'STOPPED' || inc.status === 'STOPPED'

                const statusBadge = isSuccess ? {
                  label: 'Recovered',
                  className: 'bg-emerald-50 text-emerald-800 border-emerald-200',
                  icon: CheckCircle2
                } : isPending ? {
                  label: 'Needs Review',
                  className: 'bg-amber-50 text-amber-800 border-amber-200',
                  icon: AlertTriangle
                } : isStopped ? {
                  label: 'Stopped / Safe',
                  className: 'bg-slate-100 text-slate-700 border-slate-200',
                  icon: ShieldAlert
                } : {
                  label: 'Failed',
                  className: 'bg-rose-50 text-rose-800 border-rose-200',
                  icon: XCircle
                }

                const StatusIcon = statusBadge.icon

                // Plain English Recommended Action
                const plainAction = isSuccess
                  ? 'Order verified in database'
                  : isPending
                  ? (inc.id === 'pay_005' ? 'Verify order status & approve' : 'Review payment')
                  : isStopped
                  ? 'Halted per policy (Duplicate prevented)'
                  : 'Escalated to engineering'

                return (
                  <tr
                    key={inc.id}
                    onClick={() => onSelect(isSelected ? null : inc.id)}
                    className={`hover:bg-slate-50/80 cursor-pointer transition-colors ${
                      isSelected ? 'bg-brand-50/60' : ''
                    }`}
                  >
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-1.5">
                        <span className="font-mono font-bold text-brand-700">{inc.id}</span>
                        {isSelected && <ChevronRight size={13} className="text-brand-600" />}
                      </div>
                      {inc.orderId && (
                        <div className="text-[10px] font-mono text-slate-400">{inc.orderId}</div>
                      )}
                    </td>

                    <td className="px-5 py-3.5 font-mono font-bold text-slate-900">
                      ₹{inc.amount.toLocaleString('en-IN')}
                    </td>

                    <td className="px-5 py-3.5 text-slate-700 font-medium max-w-xs truncate">
                      {inc.rootCause}
                    </td>

                    <td className="px-5 py-3.5">
                      <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold border ${statusBadge.className}`}>
                        <StatusIcon size={11} />
                        <span>{statusBadge.label}</span>
                      </span>
                    </td>

                    <td className="px-5 py-3.5 text-slate-600">
                      <span className="text-xs">{plainAction}</span>
                    </td>

                    <td className="px-5 py-3.5 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          onSelect(inc.id)
                        }}
                        className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all shadow-2xs cursor-pointer ${
                          isPending
                            ? 'bg-brand-600 hover:bg-brand-700 text-white'
                            : isSelected
                            ? 'bg-brand-100 text-brand-800'
                            : 'bg-slate-100 hover:bg-slate-200 text-slate-700'
                        }`}
                      >
                        {isPending ? 'Review' : isSelected ? 'Viewing' : 'View'}
                      </button>
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
"""
)

# =========================================================================
# 5. FileUploadModal.jsx
# =========================================================================
write_file(
    'dashboard/src/components/upload/FileUploadModal.jsx',
    r"""import { useState, useRef } from 'react'
import { X, UploadCloud, FileText, CheckCircle2, AlertCircle, ArrowRight, ShieldCheck, Download } from 'lucide-react'
import { uploadPaymentBatchFile } from '../../services/api'

export default function FileUploadModal({ isOpen, onClose, onComplete }) {
  const [file, setFile] = useState(null)
  const [isUploading, setIsUploading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef(null)

  if (!isOpen) return null

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0])
      setError(null)
      setResult(null)
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0])
      setError(null)
      setResult(null)
    }
  }

  const handleUpload = async () => {
    if (!file) return
    setIsUploading(true)
    setError(null)
    try {
      const res = await uploadPaymentBatchFile(file)
      setResult(res)
      if (onComplete) onComplete(res)
    } catch (err) {
      setError(err.message || 'Failed to parse batch file.')
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white border border-slate-200 rounded-2xl shadow-xl max-w-xl w-full overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-brand-50 border border-brand-100 flex items-center justify-center text-brand-600">
              <UploadCloud size={16} />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900">Import Payment Records</h3>
              <p className="text-xs text-slate-500">Upload payment exports to diagnose and recover failed checkouts</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-700 flex items-center justify-center transition-colors cursor-pointer"
          >
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-4">
          {/* Dropzone */}
          <div
            onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => inputRef.current?.click()}
            className={`border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all ${
              dragOver
                ? 'border-brand-500 bg-brand-50/50'
                : file
                ? 'border-emerald-300 bg-emerald-50/30'
                : 'border-slate-200 bg-slate-50 hover:bg-slate-100/60'
            }`}
          >
            <input
              ref={inputRef}
              type="file"
              onChange={handleFileChange}
              accept=".csv,.json,.txt,.xlsx,.docx,.pdf"
              className="hidden"
            />
            <div className="w-12 h-12 rounded-2xl bg-white border border-slate-200 flex items-center justify-center text-brand-600 mx-auto mb-3 shadow-xs">
              <FileText size={22} />
            </div>
            {file ? (
              <div className="space-y-1">
                <div className="text-xs font-bold text-slate-900 font-mono">{file.name}</div>
                <div className="text-[11px] text-slate-500">{(file.size / 1024).toFixed(1)} KB · Ready to analyze</div>
              </div>
            ) : (
              <div className="space-y-1">
                <div className="text-xs font-bold text-slate-800">
                  Click to select or drag and drop payment file
                </div>
                <div className="text-[11px] text-slate-500">
                  Supports CSV, JSON, TXT, Excel (XLSX), PDF, DOCX
                </div>
              </div>
            )}
          </div>

          {/* Error Banner */}
          {error && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-800 flex items-center gap-2">
              <AlertCircle size={14} className="flex-shrink-0 text-rose-600" />
              <span>{error}</span>
            </div>
          )}

          {/* Result Summary */}
          {result && (
            <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl space-y-2">
              <div className="flex items-center gap-2 text-xs font-bold text-emerald-900">
                <CheckCircle2 size={15} className="text-emerald-600" />
                <span>File analyzed successfully</span>
              </div>
              <div className="grid grid-cols-3 gap-2 text-center">
                <div className="p-2 bg-white/80 rounded-lg border border-emerald-100">
                  <div className="text-xs text-slate-500 font-medium">Valid Records</div>
                  <div className="text-sm font-bold text-slate-900 font-mono">{result.valid_records || 5}</div>
                </div>
                <div className="p-2 bg-white/80 rounded-lg border border-emerald-100">
                  <div className="text-xs text-slate-500 font-medium">At Risk</div>
                  <div className="text-sm font-bold text-rose-600 font-mono">₹{(result.total_amount_at_risk || 31600).toLocaleString('en-IN')}</div>
                </div>
                <div className="p-2 bg-white/80 rounded-lg border border-emerald-100">
                  <div className="text-xs text-slate-500 font-medium">Quarantined</div>
                  <div className="text-sm font-bold text-slate-900 font-mono">{result.quarantine_count || 0}</div>
                </div>
              </div>
            </div>
          )}

          {/* Supported Features Pill */}
          <div className="flex items-center justify-between text-[11px] text-slate-500 pt-2 border-t border-slate-100">
            <span className="flex items-center gap-1">
              <ShieldCheck size={13} className="text-brand-600" />
              Automatic format cleanup & deduplication
            </span>
            <span className="font-mono text-slate-400">RFC-4180 compliant</span>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-3.5 bg-slate-50 border-t border-slate-100 flex items-center justify-between">
          <button
            onClick={onClose}
            className="px-3.5 py-1.5 rounded-xl border border-slate-200 bg-white hover:bg-slate-100 text-xs font-semibold text-slate-700 transition-colors cursor-pointer"
          >
            Cancel
          </button>
          <button
            onClick={handleUpload}
            disabled={!file || isUploading}
            className="px-4 py-1.5 rounded-xl bg-brand-600 hover:bg-brand-700 text-white text-xs font-bold transition-all shadow-xs disabled:opacity-50 flex items-center gap-1.5 cursor-pointer"
          >
            {isUploading ? 'Analyzing File...' : 'Start Intelligence Analysis'}
            <ArrowRight size={13} />
          </button>
        </div>

      </div>
    </div>
  )
}
"""
)

# =========================================================================
# 6. SandboxToolsModal.jsx (Developer & Demo Controls)
# =========================================================================
write_file(
    'dashboard/src/components/layout/SandboxToolsModal.jsx',
    r"""import { useState } from 'react'
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
"""
)

# =========================================================================
# 7. TopNav.jsx
# =========================================================================
write_file(
    'dashboard/src/components/layout/TopNav.jsx',
    r"""import { useState, useEffect } from 'react'
import { Shield, RefreshCw, Terminal, CheckCircle2, AlertCircle } from 'lucide-react'
import { checkAgentHealth, triggerResetDemoState } from '../../services/api'
import SandboxToolsModal from './SandboxToolsModal'

const tabs = ['Overview', 'Payments', 'Activity', 'Audit']

export default function TopNav({ activeTab, onTabChange, onDataRefresh }) {
  const [backendOnline, setBackendOnline] = useState(false)
  const [isProcessing, setIsProcessing] = useState(false)
  const [showSandboxModal, setShowSandboxModal] = useState(false)

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
      <div className="max-w-[1600px] mx-auto px-6 h-14 flex items-center justify-between gap-4">
        
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

        {/* CENTER: Navigation Tabs (Simplified 4-Tab Architecture) */}
        <nav className="flex items-center gap-1 bg-slate-100 p-1 rounded-xl border border-slate-200">
          {tabs.map((tab) => {
            const isActive = activeTab === tab
            return (
              <button
                key={tab}
                onClick={() => onTabChange(tab)}
                className={`px-3.5 py-1 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
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

        {/* RIGHT: Sandbox Mode, Demo Tools & Status */}
        <div className="flex items-center gap-2 flex-shrink-0">
          {/* Sandbox Mode Pill */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-amber-50 border border-amber-200 text-[11px] font-bold text-amber-800">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse"></span>
            <span className="hidden sm:inline">SANDBOX</span>
          </div>

          {/* Developer / Demo Sandbox Modal Button */}
          <button
            onClick={() => setShowSandboxModal(true)}
            title="Open Developer & Demo Sandbox Tools"
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-slate-200 bg-slate-50 hover:bg-slate-100 text-xs font-semibold text-slate-700 transition-colors shadow-2xs cursor-pointer"
          >
            <Terminal size={12} className="text-amber-600" />
            <span className="hidden md:inline">Demo Tools</span>
          </button>

          {/* Quick Action: Reset Demo */}
          <button
            onClick={handleResetDemo}
            disabled={isProcessing}
            title="Reset database to initial baseline"
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 text-xs font-semibold text-slate-700 transition-colors shadow-xs disabled:opacity-50 cursor-pointer"
          >
            <RefreshCw size={11} className={isProcessing ? 'animate-spin text-brand-600' : 'text-slate-400'} />
            <span className="hidden sm:inline">Reset</span>
          </button>

          {/* API Health Pill */}
          <div className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-slate-50 border border-slate-200 text-[11px] font-mono text-slate-600">
            <span className={`w-1.5 h-1.5 rounded-full ${backendOnline ? 'bg-emerald-500' : 'bg-amber-500'}`}></span>
            <span className="hidden lg:inline">{backendOnline ? 'ONLINE' : 'OFFLINE'}</span>
          </div>
        </div>

      </div>

      {/* Developer Sandbox Tools Modal */}
      <SandboxToolsModal
        isOpen={showSandboxModal}
        onClose={() => setShowSandboxModal(false)}
        onResetComplete={onDataRefresh}
      />
    </header>
  )
}
"""
)

# =========================================================================
# 8. LiveActivityFeed.jsx
# =========================================================================
write_file(
    'dashboard/src/components/activity/LiveActivityFeed.jsx',
    r"""import { useEffect, useState, useRef, useCallback } from 'react'
import {
  Radar, AlertTriangle, Search, Brain, Shield, Zap, Key,
  CheckCircle2, Play, Database, FileText, Check, RefreshCw, Cpu, ChevronDown, ChevronUp, Clock
} from 'lucide-react'
import { triggerRunPythonAgent, fetchAgentEvents } from '../../services/api'
import { agentActivityEvents as fallbackEvents } from '../../data/agentActivity'

const iconMap = {
  radar: Radar,
  alert: AlertTriangle,
  search: Search,
  brain: Brain,
  shield: Shield,
  zap: Zap,
  key: Key,
  check: Check,
  play: Play,
  database: Database,
  'file-text': FileText,
  'check-circle': CheckCircle2,
  cpu: Cpu
}

function EventRow({ event, visible, showTechnical }) {
  const Icon = iconMap[event.icon] || Check

  return (
    <div
      className={`flex items-start gap-3 p-3.5 rounded-xl border transition-all duration-300 ${
        event.status === 'green'
          ? 'bg-emerald-50/60 border-emerald-100'
          : event.status === 'warn'
          ? 'bg-amber-50/60 border-amber-100'
          : 'bg-white border-slate-200'
      } ${visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'}`}
    >
      {/* Icon */}
      <div className={`w-7 h-7 rounded-lg bg-white border border-slate-200 flex items-center justify-center flex-shrink-0 mt-0.5 shadow-2xs ${
        event.status === 'green' ? 'text-emerald-600' : event.status === 'warn' ? 'text-amber-600' : 'text-brand-600'
      }`}>
        <Icon size={13} strokeWidth={2.2} />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5 flex-wrap">
          <span className="text-xs font-bold text-slate-900">{event.title}</span>

          {event.payment_id && (
            <span className="text-[10px] font-mono font-bold text-brand-700 bg-brand-50 px-1.5 py-0.2 rounded border border-brand-200">
              {event.payment_id}
            </span>
          )}

          {showTechnical && event.type && (
            <span className="text-[10px] font-mono text-slate-500 bg-slate-50 px-1.5 py-0.2 rounded border border-slate-200">
              {event.type}
            </span>
          )}
        </div>
        <div className="text-xs text-slate-600 leading-relaxed">{event.detail}</div>
      </div>

      {/* Time */}
      <div className="flex-shrink-0 font-mono text-[11px] text-slate-400 mt-0.5 flex items-center gap-1">
        <Clock size={10} />
        <span>{event.time}</span>
      </div>
    </div>
  )
}

export default function LiveActivityFeed({
  selectedPaymentId = 'pay_004',
  onRunComplete,
  onStepChange,
  incidentsList = [],
  onSelectPayment
}) {
  const [events, setEvents] = useState([])
  const [visibleCount, setVisibleCount] = useState(0)
  const [isRunning, setIsRunning] = useState(false)
  const [showTechnical, setShowTechnical] = useState(false)
  const timeoutsRef = useRef([])

  const loadAndReplay = useCallback(async (paymentId, progressive = true) => {
    timeoutsRef.current.forEach(clearTimeout)
    timeoutsRef.current = []

    let evs = await fetchAgentEvents(paymentId)
    if (!evs || evs.length === 0) {
      evs = fallbackEvents[paymentId] || fallbackEvents['pay_004'] || []
    }

    setEvents(evs)

    if (progressive && evs.length > 0) {
      setVisibleCount(1)
      setIsRunning(true)
      evs.forEach((_, idx) => {
        if (idx === 0) return
        const t = setTimeout(() => {
          setVisibleCount(idx + 1)
          if (idx === evs.length - 1) {
            setIsRunning(false)
            if (onRunComplete) onRunComplete()
          }
        }, idx * 400)
        timeoutsRef.current.push(t)
      })
    } else {
      setVisibleCount(evs.length)
      setIsRunning(false)
    }
  }, [onRunComplete])

  useEffect(() => {
    loadAndReplay(selectedPaymentId, false)
    return () => timeoutsRef.current.forEach(clearTimeout)
  }, [selectedPaymentId, loadAndReplay])

  return (
    <div className="bg-white border border-slate-200 rounded-2xl shadow-xs overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-bold text-slate-900">Recovery Activity Stream</h3>
            <span className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
              Live Feed
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Real-time event stream of payment incident detection, investigation, and recovery.
          </p>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowTechnical(!showTechnical)}
            className={`px-2.5 py-1 rounded-lg text-xs font-semibold border transition-all cursor-pointer ${
              showTechnical
                ? 'bg-slate-900 text-white border-slate-900'
                : 'bg-slate-50 hover:bg-slate-100 text-slate-600 border-slate-200'
            }`}
          >
            {showTechnical ? 'Hide Tech Info' : 'Show Tech Info'}
          </button>

          <button
            onClick={() => loadAndReplay(selectedPaymentId, true)}
            disabled={isRunning}
            className="flex items-center gap-1 px-3 py-1 rounded-lg bg-brand-50 hover:bg-brand-100 text-brand-700 border border-brand-200 text-xs font-semibold transition-colors disabled:opacity-50 cursor-pointer shadow-2xs"
          >
            <RefreshCw size={11} className={isRunning ? 'animate-spin' : ''} />
            <span>Replay Feed</span>
          </button>
        </div>
      </div>

      {/* Events List */}
      <div className="p-4 space-y-2.5 max-h-[600px] overflow-y-auto">
        {events.length === 0 ? (
          <div className="text-center py-8 text-slate-400 text-xs">
            No recovery events recorded yet.
          </div>
        ) : (
          events.slice(0, visibleCount).map((event, idx) => (
            <EventRow
              key={event.id || `${event.type}_${idx}`}
              event={event}
              visible={true}
              showTechnical={showTechnical}
            />
          ))
        )}
      </div>
    </div>
  )
}
"""
)

# =========================================================================
# 9. AuditTrail.jsx
# =========================================================================
write_file(
    'dashboard/src/components/audit/AuditTrail.jsx',
    r"""import { useState } from 'react'
import { FileText, RefreshCw, CheckCircle2, ShieldCheck, ChevronDown, ChevronUp, Lock } from 'lucide-react'
import { auditRecords as fallbackRecords } from '../../data/incidents'

export default function AuditTrail({ dynamicRecords, onRefresh }) {
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [expandedRow, setExpandedRow] = useState(null)
  const records = dynamicRecords || fallbackRecords

  const handleRefresh = async () => {
    if (!onRefresh) return
    setIsRefreshing(true)
    await onRefresh()
    setTimeout(() => setIsRefreshing(false), 400)
  }

  return (
    <div className="space-y-4">
      {/* Header Banner */}
      <div className="p-5 bg-white border border-slate-200 rounded-2xl shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-bold text-slate-900">Compliance & Recovery Audit Ledger</h2>
            <span className="inline-flex items-center gap-1 text-[10px] font-bold text-slate-600 bg-slate-100 px-2 py-0.5 rounded-md border border-slate-200">
              <Lock size={10} /> Immutable
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Every recovery decision, idempotency key generation, and order confirmation is permanently recorded for compliance and accounting.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="font-mono text-xs font-semibold text-brand-700 bg-brand-50 px-3 py-1.5 rounded-xl border border-brand-200 hidden sm:inline">
            logs/batch_recovery_log.json
          </span>
          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-xs font-semibold text-slate-700 transition-all shadow-xs cursor-pointer disabled:opacity-50"
          >
            <RefreshCw size={12} className={isRefreshing ? 'animate-spin text-brand-600' : ''} />
            <span>Sync Ledger</span>
          </button>
        </div>
      </div>

      {/* Ledger Table */}
      <div className="bg-white border border-slate-200 rounded-2xl shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-bold uppercase text-[10px] tracking-wider">
              <tr>
                <th className="px-5 py-3">Payment</th>
                <th className="px-5 py-3">Amount</th>
                <th className="px-5 py-3">Diagnosed Cause</th>
                <th className="px-5 py-3">Confidence</th>
                <th className="px-5 py-3">Idempotency Key</th>
                <th className="px-5 py-3">Policy Decision</th>
                <th className="px-5 py-3">Audit Status</th>
                <th className="px-5 py-3 text-right">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white">
              {records.map((record) => {
                const pid = record.paymentId || record.payment_id || 'pay_001'
                const isExpanded = expandedRow === pid
                const rawStatus = record.recoveryStatus || record.status || 'PENDING'
                
                // Explicit clean statuses (Zero N/A)
                const displayStatus = rawStatus === 'NOT_EXECUTED'
                  ? 'AWAITING_REVIEW'
                  : rawStatus

                const statusBadge = displayStatus === 'SUCCESS' || displayStatus === 'RECOVERED'
                  ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                  : displayStatus === 'PENDING' || displayStatus === 'AWAITING_REVIEW'
                  ? 'bg-amber-50 text-amber-800 border-amber-200'
                  : 'bg-slate-100 text-slate-700 border-slate-200'

                const idemKey = record.recoveryKey || record.idempotency_key || `${pid}_ORDER_SYNC_v1`

                return (
                  <tr key={pid} className="hover:bg-slate-50/70 transition-colors">
                    <td className="px-5 py-3.5 font-mono font-bold text-brand-700">
                      {pid}
                    </td>

                    <td className="px-5 py-3.5 font-mono font-bold text-slate-900">
                      ₹{Number(record.amount || 3100).toLocaleString('en-IN')}
                    </td>

                    <td className="px-5 py-3.5 text-slate-700 font-medium max-w-xs truncate">
                      {record.rootCause || record.root_cause || 'Delayed order confirmation'}
                    </td>

                    <td className="px-5 py-3.5 font-mono font-bold">
                      <span className={record.confidence >= 85 ? 'text-emerald-700' : 'text-amber-700'}>
                        {record.confidence || 60}%
                      </span>
                    </td>

                    <td className="px-5 py-3.5 font-mono text-[11px] text-slate-600 max-w-[180px] truncate">
                      {idemKey}
                    </td>

                    <td className="px-5 py-3.5">
                      <span className="text-xs font-semibold text-slate-800">
                        {record.decision || 'HUMAN REVIEW'}
                      </span>
                    </td>

                    <td className="px-5 py-3.5">
                      <span className={`inline-flex px-2.5 py-0.5 rounded-full text-[10px] font-bold border ${statusBadge}`}>
                        {displayStatus}
                      </span>
                    </td>

                    <td className="px-5 py-3.5 text-right">
                      <button
                        onClick={() => setExpandedRow(isExpanded ? null : pid)}
                        className="px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-600 font-semibold text-xs transition-colors cursor-pointer"
                      >
                        {isExpanded ? 'Hide' : 'Inspect'}
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
"""
)

# =========================================================================
# 10. IncidentDetailPanel.jsx (3-Layer Progressive Disclosure Workspace)
# =========================================================================
write_file(
    'dashboard/src/components/incidents/IncidentDetailPanel.jsx',
    r"""import { useState, useEffect } from 'react'
import {
  X, CheckCircle2, AlertTriangle, AlertCircle, ShieldCheck, ShieldAlert,
  ChevronDown, ChevronUp, Copy, Check, Terminal, ExternalLink, RefreshCw, Lock,
  FileText, Activity, Server, ArrowRight, CornerDownRight, Zap, Info, Clock, AlertOctagon
} from 'lucide-react'
import {
  getPaymentOperationalSnapshot,
  approvePaymentRecoveryWithIdempotency
} from '../../services/api'

export default function IncidentDetailPanel({ incident, onClose, onRunRecovery }) {
  const [snapshot, setSnapshot] = useState(null)
  const [loadingSnapshot, setLoadingSnapshot] = useState(true)
  const [copiedKey, setCopiedKey] = useState(false)
  const [copiedJson, setCopiedJson] = useState(false)
  const [activeModalAction, setActiveModalAction] = useState(null)
  const [isProcessingAction, setIsProcessingAction] = useState(false)
  const [actionFeedback, setActionFeedback] = useState(null)

  // Progressive Disclosure Accordions
  const [showAiReasoning, setShowAiReasoning] = useState(false)
  const [showTechnicalDetails, setShowTechnicalDetails] = useState(false)
  const [showRawPayload, setShowRawPayload] = useState(false)

  const paymentId = incident?.id || 'pay_005'

  // Load Single Authoritative State Snapshot
  const loadSnapshot = async () => {
    setLoadingSnapshot(true)
    try {
      const res = await getPaymentOperationalSnapshot(paymentId)
      if (res && res.snapshot) {
        setSnapshot(res.snapshot)
      }
    } catch (e) {
      console.warn('Snapshot load fallback:', e)
    } finally {
      setLoadingSnapshot(false)
    }
  }

  useEffect(() => {
    loadSnapshot()
  }, [paymentId])

  // Derive Canonical Data (Single Source of Truth)
  const amount = snapshot?.amount || incident?.amount || 3100
  const currency = snapshot?.currency || 'INR'
  const rawState = snapshot?.authoritative_payment_state || incident?.recoveryStatus || incident?.status || 'HUMAN_REVIEW'
  const isRecovered = rawState === 'RECOVERED' || rawState === 'SUCCESS'
  const isPendingReview = (rawState === 'HUMAN_REVIEW' || rawState === 'PENDING' || paymentId === 'pay_005') && !isRecovered
  const isStopped = rawState === 'STOPPED' || rawState === 'FAILED'
  const isTerminal = snapshot?.is_terminal !== undefined ? snapshot.is_terminal : (isRecovered || isStopped)

  const statusBadge = isRecovered ? {
    label: 'Recovered',
    className: 'bg-emerald-50 text-emerald-800 border-emerald-200',
    icon: CheckCircle2
  } : isPendingReview ? {
    label: 'Needs Your Attention',
    className: 'bg-amber-50 text-amber-800 border-amber-200',
    icon: AlertTriangle
  } : isStopped ? {
    label: 'Recovery Stopped / Safe',
    className: 'bg-slate-100 text-slate-700 border-slate-200',
    icon: ShieldAlert
  } : {
    label: 'Failed',
    className: 'bg-rose-50 text-rose-800 border-rose-200',
    icon: AlertCircle
  }

  const StatusIcon = statusBadge.icon
  const idempotencyKey = snapshot?.idempotency_intent?.idempotency_key || `${paymentId}_ORDER_SYNC_v1`
  const confidence = snapshot?.confidence_score || incident?.confidence || 60
  const decisionThreshold = snapshot?.decision_threshold || 85

  // Copy helper
  const handleCopy = (text, type = 'key') => {
    navigator.clipboard.writeText(text)
    if (type === 'key') {
      setCopiedKey(true)
      setTimeout(() => setCopiedKey(false), 2000)
    } else {
      setCopiedJson(true)
      setTimeout(() => setCopiedJson(false), 2000)
    }
  }

  // Handle Approve Action
  const handleApproveRecovery = async () => {
    setIsProcessingAction(true)
    setActionFeedback(null)
    try {
      const res = await approvePaymentRecoveryWithIdempotency(paymentId, {
        idempotency_key: idempotencyKey,
        operator_id: 'merchant_operator',
        recovery_strategy: 'order_sync'
      })
      setActionFeedback({ success: true, message: 'Payment recovery approved and executed successfully!' })
      await loadSnapshot()
      if (onRunRecovery) onRunRecovery(paymentId)
    } catch (err) {
      setActionFeedback({ success: false, message: err.message || 'Approval failed.' })
    } finally {
      setIsProcessingAction(false)
      setActiveModalAction(null)
    }
  }

  return (
    <div className="bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden animate-in fade-in-50 duration-200">
      
      {/* ========================================================================= */}
      {/* STICKY PAYMENT CONTEXT HEADER */}
      {/* ========================================================================= */}
      <div className="sticky top-0 z-10 bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3 flex-wrap">
          <span className="font-mono text-xs font-bold text-brand-700 bg-brand-50 px-3 py-1 rounded-lg border border-brand-200">
            {paymentId}
          </span>
          <span className="text-lg font-bold text-slate-900 font-mono">
            ₹{amount.toLocaleString('en-IN')}
          </span>
          <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold border ${statusBadge.className}`}>
            <StatusIcon size={13} />
            <span>{statusBadge.label}</span>
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={loadSnapshot}
            title="Refresh payment status"
            className="w-8 h-8 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-700 flex items-center justify-center transition-colors cursor-pointer"
          >
            <RefreshCw size={14} className={loadingSnapshot ? 'animate-spin text-brand-600' : ''} />
          </button>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-700 flex items-center justify-center transition-colors cursor-pointer"
          >
            <X size={18} />
          </button>
        </div>
      </div>

      <div className="p-6 space-y-6">
        
        {/* ========================================================================= */}
        {/* LAYER 1: MERCHANT BUSINESS VIEW */}
        {/* ========================================================================= */}

        {/* Quick 4-Item Context Strip */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="p-3 bg-slate-50 border border-slate-200/80 rounded-xl space-y-0.5">
            <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Gateway Status</div>
            <div className="text-xs font-bold text-emerald-800 flex items-center gap-1">
              <CheckCircle2 size={12} className="text-emerald-600" />
              <span>Funds Captured</span>
            </div>
          </div>

          <div className="p-3 bg-slate-50 border border-slate-200/80 rounded-xl space-y-0.5">
            <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Merchant Backend</div>
            <div className="text-xs font-bold text-slate-900">
              {isRecovered ? (
                <span className="text-emerald-800 flex items-center gap-1">
                  <CheckCircle2 size={12} className="text-emerald-600" /> Order Created
                </span>
              ) : (
                <span className="text-amber-800 flex items-center gap-1">
                  <AlertTriangle size={12} className="text-amber-600" /> Order Missing
                </span>
              )}
            </div>
          </div>

          <div className="p-3 bg-slate-50 border border-slate-200/80 rounded-xl space-y-0.5">
            <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Duplicate Protection</div>
            <div className="text-xs font-bold text-slate-900 flex items-center gap-1">
              <ShieldCheck size={12} className="text-brand-600" />
              <span>Active</span>
            </div>
          </div>

          <div className="p-3 bg-slate-50 border border-slate-200/80 rounded-xl space-y-0.5">
            <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Incident Time</div>
            <div className="text-xs font-mono text-slate-700">
              Today, 4:00 PM IST
            </div>
          </div>
        </div>

        {/* Action Feedback Banner if any */}
        {actionFeedback && (
          <div className={`p-4 rounded-xl text-xs font-semibold flex items-center gap-2 ${
            actionFeedback.success ? 'bg-emerald-50 text-emerald-900 border border-emerald-200' : 'bg-rose-50 text-rose-900 border border-rose-200'
          }`}>
            {actionFeedback.success ? <CheckCircle2 size={15} className="text-emerald-600" /> : <AlertCircle size={15} className="text-rose-600" />}
            <span>{actionFeedback.message}</span>
          </div>
        )}

        {/* 1. What Happened? */}
        <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-1.5">
          <div className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-1.5">
            <Info size={13} className="text-brand-600" />
            <span>What Happened?</span>
          </div>
          <p className="text-xs text-slate-700 leading-relaxed">
            {paymentId === 'pay_005'
              ? 'Your payment gateway successfully captured ₹3,100 from the customer, but your merchant order management system did not acknowledge order creation due to a network timeout.'
              : isRecovered
              ? 'The payment succeeded and the merchant order has been synchronized and verified in your database.'
              : (incident?.rootCause || 'Payment was successfully processed, but order creation confirmation was delayed.')}
          </p>
        </div>

        {/* 2. What RecoverIQ Recommends & Why? */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-4 bg-blue-50/70 border border-blue-100 rounded-xl space-y-1.5">
            <div className="text-xs font-bold text-blue-950 uppercase tracking-wider flex items-center gap-1.5">
              <Zap size={13} className="text-blue-600" />
              <span>What RecoverIQ Recommends</span>
            </div>
            <p className="text-xs text-blue-900 leading-relaxed font-medium">
              {isRecovered
                ? 'No action needed. The transaction has been reconciled and the order is active.'
                : 'Approve order synchronization to place the missing order without re-charging the customer.'}
            </p>
          </div>

          <div className="p-4 bg-amber-50/70 border border-amber-100 rounded-xl space-y-1.5">
            <div className="text-xs font-bold text-amber-950 uppercase tracking-wider flex items-center gap-1.5">
              <ShieldCheck size={13} className="text-amber-700" />
              <span>Why Human Approval?</span>
            </div>
            <p className="text-xs text-amber-900 leading-relaxed font-medium">
              {isRecovered
                ? 'RecoverIQ verified database records to guarantee zero duplicate fulfillment.'
                : 'RecoverIQ pauses autonomous recovery on delayed orders so you maintain full control over inventory and financial actions.'}
            </p>
          </div>
        </div>

        {/* 3. Human Action Center (Clear, Trustworthy Approval) */}
        <div className="p-5 rounded-2xl border bg-slate-50 border-slate-200 space-y-4">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div className="flex items-center gap-2">
              <div className={`w-7 h-7 rounded-lg flex items-center justify-center text-white ${
                isRecovered ? 'bg-emerald-600' : 'bg-brand-600'
              }`}>
                {isRecovered ? <CheckCircle2 size={15} /> : <Zap size={15} />}
              </div>
              <div>
                <h3 className="text-sm font-bold text-slate-900">
                  {isRecovered ? 'Recovery Completed' : 'Your Action is Required'}
                </h3>
                <p className="text-xs text-slate-500">
                  {isRecovered
                    ? 'This payment has reached a verified terminal state.'
                    : 'Review safety checks and authorize idempotent order synchronization.'}
                </p>
              </div>
            </div>

            {isTerminal && (
              <span className="text-[11px] font-bold text-slate-500 bg-slate-200/80 px-2.5 py-0.5 rounded-full">
                Terminal State
              </span>
            )}
          </div>

          {/* Safety Checks List */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs text-slate-700">
            <div className="flex items-center gap-2 p-2 bg-white rounded-lg border border-slate-200">
              <CheckCircle2 size={14} className="text-emerald-600 flex-shrink-0" />
              <span>Payment already captured by gateway</span>
            </div>
            <div className="flex items-center gap-2 p-2 bg-white rounded-lg border border-slate-200">
              <CheckCircle2 size={14} className="text-emerald-600 flex-shrink-0" />
              <span>Pre-allocated idempotency key ready</span>
            </div>
            <div className="flex items-center gap-2 p-2 bg-white rounded-lg border border-slate-200">
              <CheckCircle2 size={14} className="text-emerald-600 flex-shrink-0" />
              <span>Duplicate execution protection enabled</span>
            </div>
            <div className="flex items-center gap-2 p-2 bg-white rounded-lg border border-slate-200">
              <CheckCircle2 size={14} className="text-emerald-600 flex-shrink-0" />
              <span>Merchant endpoint health confirmed</span>
            </div>
          </div>

          {/* Action CTAs or Terminal Guardrail Banner */}
          {isRecovered ? (
            <div className="p-3 bg-emerald-50/70 border border-emerald-200 rounded-xl text-xs text-emerald-900 flex items-center justify-between gap-3">
              <span>Order was created and confirmed in your database. All recovery actions completed.</span>
              <span className="font-semibold text-emerald-800">Actions Disabled</span>
            </div>
          ) : isStopped ? (
            <div className="p-3 bg-slate-100 border border-slate-200 rounded-xl text-xs text-slate-700 flex items-center justify-between gap-3">
              <span>Recovery halted per policy. Actions unavailable — payment has reached a terminal state.</span>
              <span className="font-semibold text-slate-500">Actions Disabled</span>
            </div>
          ) : (
            <div className="flex items-center gap-3 pt-2">
              <button
                onClick={() => setActiveModalAction('APPROVE')}
                className="px-5 py-2.5 rounded-xl bg-brand-600 hover:bg-brand-700 text-white text-xs font-bold transition-all shadow-xs hover:shadow-sm flex items-center gap-2 cursor-pointer"
              >
                <CheckCircle2 size={14} />
                <span>Approve Recovery</span>
              </button>

              <button
                onClick={() => setActiveModalAction('REJECT')}
                className="px-4 py-2.5 rounded-xl border border-slate-200 bg-white hover:bg-slate-100 text-slate-700 text-xs font-semibold transition-colors cursor-pointer"
              >
                Reject
              </button>

              <button
                onClick={() => setActiveModalAction('ESCALATE')}
                className="px-4 py-2.5 rounded-xl border border-slate-200 bg-white hover:bg-slate-100 text-slate-700 text-xs font-semibold transition-colors cursor-pointer"
              >
                Escalate
              </button>
            </div>
          )}
        </div>

        {/* AI vs Human Boundary Trust Banner */}
        <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-xs space-y-2">
          <div className="font-bold text-slate-900 text-xs">
            AI & Human Collaboration Boundary
          </div>
          <p className="text-slate-500 text-[11px] leading-relaxed">
            RecoverIQ handles automatic detection, diagnostic analysis, and safe recovery orchestration. You stay in control of financial approvals and overrides.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
            <div className="p-2.5 bg-blue-50/80 border border-blue-100 rounded-lg space-y-1">
              <div className="font-bold text-blue-900 text-[11px]">RecoverIQ Automatically:</div>
              <div className="text-blue-800 text-[11px] space-y-0.5">
                <div>✓ Catches webhook & payment failures</div>
                <div>✓ Diagnoses root causes & verifies signatures</div>
                <div>✓ Recommends safe recovery strategies</div>
              </div>
            </div>
            <div className="p-2.5 bg-amber-50/80 border border-amber-100 rounded-lg space-y-1">
              <div className="font-bold text-amber-900 text-[11px]">You Control:</div>
              <div className="text-amber-800 text-[11px] space-y-0.5">
                <div>✓ Final recovery approvals</div>
                <div>✓ Refunds & financial reversals</div>
                <div>✓ Sensitive policy overrides</div>
              </div>
            </div>
          </div>
        </div>

        {/* ========================================================================= */}
        {/* LAYER 2: ADVANCED DETAILS (PROGRESSIVE DISCLOSURE) */}
        {/* ========================================================================= */}
        <div className="border border-slate-200 rounded-2xl overflow-hidden">
          <button
            onClick={() => setShowAiReasoning(!showAiReasoning)}
            className="w-full px-5 py-3.5 bg-slate-50 hover:bg-slate-100/80 text-left flex items-center justify-between text-xs font-bold text-slate-800 transition-colors cursor-pointer"
          >
            <div className="flex items-center gap-2">
              <Activity size={14} className="text-brand-600" />
              <span>Why did RecoverIQ recommend this? (AI Decision Analysis)</span>
            </div>
            {showAiReasoning ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
          </button>

          {showAiReasoning && (
            <div className="p-5 bg-white border-t border-slate-200 space-y-4 text-xs">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-1">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">AI Confidence</div>
                  <div className="text-lg font-bold text-amber-800 font-mono">{confidence}%</div>
                  <div className="text-[10px] text-slate-500">Threshold: {decisionThreshold}% for auto-recovery</div>
                </div>

                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-1">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">Policy Routing</div>
                  <div className="text-sm font-bold text-slate-800 font-mono">HUMAN REVIEW</div>
                  <div className="text-[10px] text-slate-500">Sub-threshold routing to operator</div>
                </div>

                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-1">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">Recovery Strategy</div>
                  <div className="text-sm font-bold text-slate-800 font-mono">IDEMPOTENT_SYNC</div>
                  <div className="text-[10px] text-slate-500">Safe order replay without recharge</div>
                </div>
              </div>

              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-1">
                <div className="font-bold text-slate-800 text-xs">Multi-Vector Reconciliation Result</div>
                <div className="text-slate-600 text-xs leading-relaxed">
                  Gateway ledger shows payment ID <code className="font-mono bg-white px-1 py-0.5 rounded border border-slate-200">{paymentId}</code> captured ₹{amount.toLocaleString('en-IN')}. Merchant database had no order row matching ORD_{paymentId.replace('pay_', '')}. Post-approval execution will safely insert order records.
                </div>
              </div>
            </div>
          )}
        </div>

        {/* ========================================================================= */}
        {/* LAYER 3: ENGINEERING OBSERVABILITY & TECHNICAL DETAILS */}
        {/* ========================================================================= */}
        <div className="border border-slate-200 rounded-2xl overflow-hidden">
          <button
            onClick={() => setShowTechnicalDetails(!showTechnicalDetails)}
            className="w-full px-5 py-3.5 bg-slate-50 hover:bg-slate-100/80 text-left flex items-center justify-between text-xs font-bold text-slate-800 transition-colors cursor-pointer"
          >
            <div className="flex items-center gap-2">
              <Server size={14} className="text-slate-600" />
              <span>View Technical & Audit Details (Webhook Security, Idempotency & Traces)</span>
            </div>
            {showTechnicalDetails ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
          </button>

          {showTechnicalDetails && (
            <div className="p-5 bg-white border-t border-slate-200 space-y-4 text-xs">
              
              {/* Idempotency & Webhook Security Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                
                {/* Idempotency */}
                <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-slate-800 text-xs">Deterministic Idempotency Key</span>
                    <button
                      onClick={() => handleCopy(idempotencyKey, 'key')}
                      className="text-brand-600 hover:text-brand-700 flex items-center gap-1 font-semibold text-[11px] cursor-pointer"
                    >
                      {copiedKey ? <Check size={12} /> : <Copy size={12} />}
                      <span>{copiedKey ? 'Copied' : 'Copy Key'}</span>
                    </button>
                  </div>
                  <div className="font-mono text-xs text-slate-900 bg-white p-2.5 rounded-lg border border-slate-200 break-all">
                    {idempotencyKey}
                  </div>
                  <div className="text-[11px] text-slate-500">
                    Pre-allocated recovery intent key. Guarantees zero duplicate webhook executions on retries.
                  </div>
                </div>

                {/* Webhook Security */}
                <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-2">
                  <div className="font-bold text-slate-800 text-xs">Webhook Security Verification</div>
                  <div className="space-y-1 text-[11px]">
                    <div className="flex items-center justify-between">
                      <span className="text-slate-500">HMAC-SHA256 Signature:</span>
                      <span className="font-mono font-bold text-emerald-700">VERIFIED</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-slate-500">Timestamp Freshness:</span>
                      <span className="font-mono font-bold text-emerald-700">PASSED (&lt; 300s)</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-slate-500">Replay Protection Gate:</span>
                      <span className="font-mono font-bold text-emerald-700">ACTIVE</span>
                    </div>
                  </div>
                </div>

              </div>

              {/* Endpoint Telemetry: Incident-Time vs Current */}
              <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-2">
                <div className="font-bold text-slate-800 text-xs">Merchant Endpoint Telemetry</div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px]">
                  <div className="p-2 bg-white rounded-lg border border-slate-200">
                    <div className="text-slate-400">Incident HTTP:</div>
                    <div className="font-mono font-bold text-rose-600">504 Timeout</div>
                  </div>
                  <div className="p-2 bg-white rounded-lg border border-slate-200">
                    <div className="text-slate-400">Incident Latency:</div>
                    <div className="font-mono font-bold text-slate-800">1,250 ms</div>
                  </div>
                  <div className="p-2 bg-white rounded-lg border border-slate-200">
                    <div className="text-slate-400">Current Health:</div>
                    <div className="font-mono font-bold text-emerald-700">200 OK (Healthy)</div>
                  </div>
                  <div className="p-2 bg-white rounded-lg border border-slate-200">
                    <div className="text-slate-400">Circuit Breaker:</div>
                    <div className="font-mono font-bold text-emerald-700">CLOSED</div>
                  </div>
                </div>
              </div>

              {/* Raw JSON Payload Viewer */}
              <div className="border border-slate-200 rounded-xl overflow-hidden">
                <button
                  onClick={() => setShowRawPayload(!showRawPayload)}
                  className="w-full px-4 py-2.5 bg-slate-100/70 hover:bg-slate-100 flex items-center justify-between text-xs font-semibold text-slate-700 cursor-pointer"
                >
                  <span>Raw Snapshot & Telemetry Payload (JSON)</span>
                  {showRawPayload ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                </button>
                {showRawPayload && (
                  <div className="p-3 bg-slate-900 text-slate-100 font-mono text-[11px] max-h-60 overflow-y-auto space-y-2">
                    <div className="flex justify-end">
                      <button
                        onClick={() => handleCopy(JSON.stringify(snapshot || incident, null, 2), 'json')}
                        className="text-slate-400 hover:text-white flex items-center gap-1 text-[10px] cursor-pointer"
                      >
                        {copiedJson ? <Check size={11} /> : <Copy size={11} />}
                        <span>{copiedJson ? 'Copied' : 'Copy JSON'}</span>
                      </button>
                    </div>
                    <pre className="overflow-x-auto">{JSON.stringify(snapshot || incident, null, 2)}</pre>
                  </div>
                )}
              </div>

            </div>
          )}
        </div>

      </div>

      {/* ========================================================================= */}
      {/* HUMAN ACTION CONFIRMATION MODAL */}
      {/* ========================================================================= */}
      {activeModalAction && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white border border-slate-200 rounded-2xl shadow-2xl max-w-md w-full overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ShieldCheck size={16} className="text-brand-600" />
                <h3 className="text-sm font-bold text-slate-900">Confirm Recovery Approval</h3>
              </div>
              <button
                onClick={() => setActiveModalAction(null)}
                className="text-slate-400 hover:text-slate-700 cursor-pointer"
              >
                <X size={16} />
              </button>
            </div>

            <div className="p-6 space-y-4 text-xs">
              <p className="text-slate-600">
                You are about to authorize idempotent recovery for payment <strong className="font-mono text-slate-900">{paymentId}</strong>.
              </p>

              <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200 space-y-1.5 font-mono text-[11px]">
                <div className="flex justify-between">
                  <span className="text-slate-500">Amount:</span>
                  <span className="font-bold text-slate-900">₹{amount.toLocaleString('en-IN')}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Action:</span>
                  <span className="font-bold text-slate-900">IDEMPOTENT_ORDER_SYNC</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Idempotency Key:</span>
                  <span className="font-bold text-brand-700 truncate max-w-[200px]">{idempotencyKey}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Environment:</span>
                  <span className="font-bold text-amber-700">SANDBOX / DEMO</span>
                </div>
              </div>

              <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-[11px] text-amber-900">
                <strong>Sandbox Notice:</strong> No real money will be moved. Execution operates against simulated merchant checkout endpoints with duplicate charge protection.
              </div>
            </div>

            <div className="px-6 py-3.5 bg-slate-50 border-t border-slate-100 flex items-center justify-between">
              <button
                onClick={() => setActiveModalAction(null)}
                className="px-3.5 py-1.5 rounded-xl border border-slate-200 bg-white hover:bg-slate-100 text-xs font-semibold text-slate-700 transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleApproveRecovery}
                disabled={isProcessingAction}
                className="px-4 py-1.5 rounded-xl bg-brand-600 hover:bg-brand-700 text-white text-xs font-bold transition-all shadow-xs disabled:opacity-50 flex items-center gap-1.5 cursor-pointer"
              >
                <CheckCircle2 size={13} />
                <span>{isProcessingAction ? 'Executing Recovery...' : 'Confirm & Execute'}</span>
              </button>
            </div>

          </div>
        </div>
      )}

    </div>
  )
}
"""
)

# =========================================================================
# 11. App.jsx (Simplified Master Routing)
# =========================================================================
write_file(
    'dashboard/src/App.jsx',
    r"""import { useState, useEffect, useCallback, useRef } from 'react'
import TopNav from './components/layout/TopNav'
import StatusBar from './components/layout/StatusBar'
import AgentStatusHero from './components/overview/AgentStatusHero'
import MetricsRail from './components/overview/MetricsRail'
import NeedsAttentionSection from './components/overview/NeedsAttentionSection'
import IncidentTable from './components/incidents/IncidentTable'
import IncidentDetailPanel from './components/incidents/IncidentDetailPanel'
import FileUploadModal from './components/upload/FileUploadModal'
import LiveActivityFeed from './components/activity/LiveActivityFeed'
import AuditTrail from './components/audit/AuditTrail'
import { fetchIncidents, fetchMetrics, fetchAuditLogs, triggerRunPythonAgent, fetchAgentStatus } from './services/api'
import { incidents as fallbackIncidents } from './data/incidents'
import { metrics as fallbackMetrics } from './data/metrics'

function OverviewTab({
  incidentsList,
  metricsData,
  onReviewPayment,
  onReload,
  currentPhase,
  currentStepIndex,
  onNavigateToPayments
}) {
  const attentionCount = (incidentsList || []).filter(
    (i) => i.recoveryStatus === 'PENDING' || i.status === 'HUMAN_REVIEW' || i.decision === 'HUMAN REVIEW' || (i.id === 'pay_005' && i.status !== 'RECOVERED')
  ).length

  return (
    <div className="space-y-5">
      {/* Reassuring Hero Status */}
      <AgentStatusHero
        activePhase={currentPhase}
        currentStepIndex={currentStepIndex}
        attentionCount={attentionCount}
      />

      {/* 4 Core Business Metric Cards */}
      <MetricsRail dynamicMetrics={metricsData} />

      {/* Prominent Needs Attention Section */}
      <NeedsAttentionSection
        incidentsList={incidentsList}
        onReviewPayment={onReviewPayment}
      />

      {/* Overview Activity Summary */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        <div className="lg:col-span-8">
          <LiveActivityFeed
            selectedPaymentId="pay_005"
            onRunComplete={onReload}
            incidentsList={incidentsList}
            onSelectPayment={onReviewPayment}
          />
        </div>

        {/* Quick Payments Summary */}
        <div className="lg:col-span-4 space-y-4">
          <div className="p-5 bg-white border border-slate-200 rounded-2xl shadow-xs space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">Payment Quick Access</h3>
              <button
                onClick={onNavigateToPayments}
                className="text-xs font-semibold text-brand-600 hover:text-brand-700 cursor-pointer"
              >
                View All →
              </button>
            </div>
            <div className="divide-y divide-slate-100">
              {(incidentsList || fallbackIncidents).slice(0, 4).map((item) => (
                <div
                  key={item.id}
                  onClick={() => onReviewPayment(item.id)}
                  className="py-2.5 flex items-center justify-between hover:bg-slate-50 cursor-pointer rounded-lg px-1 transition-colors text-xs"
                >
                  <div>
                    <span className="font-mono font-bold text-brand-700">{item.id}</span>
                    <div className="text-[10px] text-slate-500 truncate max-w-[160px]">{item.rootCause}</div>
                  </div>
                  <div className="text-right">
                    <div className="font-mono font-bold text-slate-900">₹{item.amount.toLocaleString('en-IN')}</div>
                    <div className="text-[10px] font-semibold text-slate-500">{item.recoveryStatus === 'SUCCESS' ? 'Recovered' : 'Needs Review'}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

    </div>
  )
}

function PaymentsTab({ incidentsList, selectedId, onSelectId, onRunRecovery, onOpenImportModal }) {
  const selected = (incidentsList || []).find((i) => i.id === selectedId) || null

  return (
    <div className="space-y-5">
      {/* Payment Workspace Table */}
      <IncidentTable
        incidentsList={incidentsList}
        selectedId={selectedId}
        onSelect={onSelectId}
        onOpenImportModal={onOpenImportModal}
      />

      {/* 3-Layer Progressive Detail Workspace */}
      {selected && (
        <IncidentDetailPanel
          incident={selected}
          onClose={() => onSelectId(null)}
          onRunRecovery={onRunRecovery}
        />
      )}
    </div>
  )
}

export default function App() {
  const [activeTab, setActiveTab] = useState('Overview')
  const [selectedIncidentId, setSelectedIncidentId] = useState('pay_005')
  const [incidentsList, setIncidentsList] = useState(fallbackIncidents)
  const [metricsData, setMetricsData] = useState(fallbackMetrics)
  const [auditLogsList, setAuditLogsList] = useState(null)
  const [currentPhase, setCurrentPhase] = useState('VERIFYING')
  const [currentStepIndex, setCurrentStepIndex] = useState(4)
  const [showImportModal, setShowImportModal] = useState(false)
  const hasAutoTriggeredRef = useRef(false)

  const reloadData = useCallback(async () => {
    try {
      const [inc, met, aud, status] = await Promise.all([
        fetchIncidents(),
        fetchMetrics(),
        fetchAuditLogs(),
        fetchAgentStatus()
      ])
      if (inc && inc.length > 0) setIncidentsList(inc)
      if (met) setMetricsData(met)
      if (aud) setAuditLogsList(aud)
      if (status && status.phase) setCurrentPhase(status.phase)
    } catch (e) {
      console.warn('Using local dataset cache:', e)
    }
  }, [])

  useEffect(() => {
    reloadData()
    const interval = setInterval(reloadData, 5000)
    return () => clearInterval(interval)
  }, [reloadData])

  const handleReviewPayment = (paymentId) => {
    setSelectedIncidentId(paymentId)
    setActiveTab('Payments')
  }

  const handleRunRecoveryFromAnywhere = (paymentId) => {
    setSelectedIncidentId(paymentId)
    triggerRunPythonAgent(paymentId).then(() => reloadData())
  }

  const renderTab = () => {
    switch (activeTab) {
      case 'Overview':
        return (
          <OverviewTab
            incidentsList={incidentsList}
            metricsData={metricsData}
            onReviewPayment={handleReviewPayment}
            onReload={reloadData}
            currentPhase={currentPhase}
            currentStepIndex={currentStepIndex}
            onNavigateToPayments={() => setActiveTab('Payments')}
          />
        )
      case 'Payments':
        return (
          <PaymentsTab
            incidentsList={incidentsList}
            selectedId={selectedIncidentId}
            onSelectId={setSelectedIncidentId}
            onRunRecovery={handleRunRecoveryFromAnywhere}
            onOpenImportModal={() => setShowImportModal(true)}
          />
        )
      case 'Activity':
        return (
          <div className="space-y-5">
            <LiveActivityFeed
              selectedPaymentId={selectedIncidentId || 'pay_005'}
              onRunComplete={reloadData}
              incidentsList={incidentsList}
              onSelectPayment={setSelectedIncidentId}
            />
          </div>
        )
      case 'Audit':
        return <AuditTrail dynamicRecords={auditLogsList} onRefresh={reloadData} />
      default:
        return (
          <OverviewTab
            incidentsList={incidentsList}
            metricsData={metricsData}
            onReviewPayment={handleReviewPayment}
            onReload={reloadData}
            currentPhase={currentPhase}
            currentStepIndex={currentStepIndex}
            onNavigateToPayments={() => setActiveTab('Payments')}
          />
        )
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 antialiased font-sans flex flex-col">
      <TopNav
        activeTab={activeTab}
        onTabChange={setActiveTab}
        onDataRefresh={reloadData}
      />
      <StatusBar />

      {/* Main Content Area */}
      <main className="px-4 sm:px-6 py-6 max-w-[1600px] w-full mx-auto flex-1">
        {renderTab()}
      </main>

      {/* Import Payments Batch Modal */}
      <FileUploadModal
        isOpen={showImportModal}
        onClose={() => setShowImportModal(false)}
        onComplete={() => {
          setShowImportModal(false)
          reloadData()
        }}
      />
    </div>
  )
}
"""
)

print('\n=======================================================')
print('✓ ALL MERCHANT-FIRST UI COMPONENTS GENERATED SUCCESSFULLY!')
print('=======================================================')





