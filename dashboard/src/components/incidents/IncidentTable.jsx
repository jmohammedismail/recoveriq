import { useState, useEffect } from 'react'
import {
  Search, Filter, ArrowUpDown, ChevronRight, CheckCircle2, AlertTriangle,
  AlertCircle, ShieldAlert, UploadCloud, RefreshCw, Layers, Check, Sparkles, FileText
} from 'lucide-react'
import { incidents as fallbackIncidents } from '../../data/incidents'

export default function IncidentTable({ incidentsList, selectedId, onSelect, onOpenImportModal, onNavigateToFileAnalysis, initialFilter }) {
  const [searchQuery, setSearchQuery] = useState('')
  const [filterState, setFilterState] = useState(initialFilter || 'ALL')
  const incidents = incidentsList || fallbackIncidents

  useEffect(() => {
    if (initialFilter) {
      setFilterState(initialFilter)
    }
  }, [initialFilter])

  // Filtering logic
  const filtered = incidents.filter((item) => {
    // 1. Text Search Filter
    const query = searchQuery.toLowerCase().trim()
    const matchesSearch = !query || 
      item.id?.toLowerCase().includes(query) ||
      item.orderId?.toLowerCase().includes(query) ||
      item.amount?.toString().includes(query) ||
      item.rootCause?.toLowerCase().includes(query)

    // 2. Status Category Filter
    const rawState = String(item.recoveryStatus || item.status || 'PENDING').toUpperCase()
    const isPay005Pending = item.id === 'pay_005' && rawState !== 'RECOVERED' && rawState !== 'SUCCESS'
    const isPay002Pending = item.id === 'pay_002' && rawState !== 'RECOVERED' && rawState !== 'SUCCESS'
    const isRecovered = (rawState === 'SUCCESS' || rawState === 'RECOVERED') && !isPay005Pending && !isPay002Pending
    const isStopped = item.id === 'pay_003' || item.id === 'pay_001' || rawState === 'STOPPED' || rawState === 'REFUNDED' || item.decision === 'STOP'
    const isNeedsAttention = (rawState === 'PENDING' || rawState === 'HUMAN_REVIEW' || rawState === 'AWAITING_REVIEW' || item.decision === 'HUMAN REVIEW' || item.decision === 'HUMAN_REVIEW' || isPay005Pending || isPay002Pending) && !isRecovered && !isStopped
    const isRecovering = (rawState === 'RECOVERING' || rawState === 'PROCESSING') && !isRecovered && !isStopped

    let matchesFilter = true

    if (filterState === 'NEEDS_ATTENTION') {
      matchesFilter = isNeedsAttention
    } else if (filterState === 'RECOVERED') {
      matchesFilter = isRecovered
    } else if (filterState === 'RECOVERING') {
      matchesFilter = isRecovering
    } else if (filterState === 'STOPPED') {
      matchesFilter = isStopped
    }

    return matchesSearch && matchesFilter
  })

  // Synchronize open detail panel with active filter:
  // If the currently selected incident does NOT match the active filter, auto-sync to first matching item or null
  useEffect(() => {
    if (selectedId && filtered.length > 0) {
      const isSelectedInFilter = filtered.some((item) => item.id === selectedId)
      if (!isSelectedInFilter) {
        onSelect(filtered[0]?.id || null)
      }
    } else if (selectedId && filtered.length === 0) {
      onSelect(null)
    }
  }, [filterState, filtered, selectedId, onSelect])

  const getStatusBadge = (item) => {
    const rawState = String(item.recoveryStatus || item.status || 'PENDING').toUpperCase()
    const isPay005Pending = item.id === 'pay_005' && rawState !== 'RECOVERED' && rawState !== 'SUCCESS'
    const isPay002Pending = item.id === 'pay_002' && rawState !== 'RECOVERED' && rawState !== 'SUCCESS'

    // 1. RECOVERED / SUCCESS
    if (rawState === 'SUCCESS' || rawState === 'RECOVERED') {
      if (!isPay005Pending && !isPay002Pending) {
        return {
          label: 'Recovered',
          className: 'bg-emerald-50 text-emerald-800 border-emerald-200',
          icon: CheckCircle2
        }
      }
    }

    // 2. STOPPED / SAFE (pay_001, pay_003, or explicit STOPPED / STOP decision)
    if (item.id === 'pay_003' || item.id === 'pay_001' || rawState === 'STOPPED' || rawState === 'REFUNDED' || item.decision === 'STOP') {
      return {
        label: 'Stopped / Safe',
        className: 'bg-slate-100 text-slate-700 border-slate-200',
        icon: ShieldAlert
      }
    }

    // 3. HUMAN REVIEW / NEEDS REVIEW (pay_002, pay_005, PENDING, HUMAN_REVIEW, AWAITING_REVIEW)
    if (rawState === 'HUMAN_REVIEW' || rawState === 'PENDING' || rawState === 'AWAITING_REVIEW' || item.decision === 'HUMAN REVIEW' || item.decision === 'HUMAN_REVIEW' || isPay005Pending || isPay002Pending) {
      return {
        label: 'Needs Review',
        className: 'bg-amber-50 text-amber-800 border-amber-200',
        icon: AlertTriangle
      }
    }

    // 4. RECOVERING / PROCESSING
    if (rawState === 'RECOVERING' || rawState === 'PROCESSING') {
      return {
        label: 'Recovering',
        className: 'bg-blue-50 text-blue-800 border-blue-200',
        icon: RefreshCw
      }
    }

    // 5. Genuine failure (if ever encountered)
    return {
      label: 'Failed',
      className: 'bg-rose-50 text-rose-800 border-rose-200',
      icon: AlertCircle
    }
  }

  return (
    <div className="bg-white border border-slate-200 rounded-2xl shadow-xs overflow-hidden">
      
      {/* Table Action Controls Header */}
      <div className="p-4 border-b border-slate-200 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-slate-50/50">
        
        {/* Search Bar */}
        <div className="relative flex-1 max-w-md">
          <Search size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by Payment ID, Order ID, Amount..."
            className="w-full pl-9 pr-4 py-1.5 rounded-xl border border-slate-200 text-xs bg-white focus:outline-hidden focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 text-slate-800 placeholder-slate-400 shadow-2xs"
          />
        </div>

        {/* Filter Pills & Actions */}
        <div className="flex items-center gap-2 overflow-x-auto flex-wrap">
          {[
            { id: 'ALL', label: 'All Payments' },
            { id: 'NEEDS_ATTENTION', label: 'Needs Attention' },
            { id: 'RECOVERING', label: 'Recovering' },
            { id: 'RECOVERED', label: 'Recovered' },
            { id: 'STOPPED', label: 'Stopped / Safe' }
          ].map((f) => (
            <button
              key={f.id}
              onClick={() => setFilterState(f.id)}
              className={`px-3 py-1 rounded-xl text-xs font-semibold whitespace-nowrap transition-all cursor-pointer ${
                filterState === f.id
                  ? 'bg-white text-brand-700 border border-brand-200 shadow-2xs'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/50'
              }`}
            >
              {f.label}
            </button>
          ))}

          {/* Import Batch / CSV Button (Embedded inside Payments) */}
          <button
            onClick={onOpenImportModal}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-[#0C66E4] hover:bg-[#0052CC] text-white text-xs font-bold transition-all shadow-xs whitespace-nowrap cursor-pointer"
          >
            <UploadCloud size={13} />
            <span>Import Batch / CSV</span>
          </button>

          {/* Analyze File Button */}
          {onNavigateToFileAnalysis && (
            <button
              onClick={onNavigateToFileAnalysis}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-xs font-bold text-slate-700 transition-colors shadow-2xs whitespace-nowrap cursor-pointer"
            >
              <FileText size={12} className="text-brand-600" />
              <span>File Analysis</span>
            </button>
          )}
        </div>

      </div>

      {/* Incident Records Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse text-xs">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50/80 text-slate-500 font-bold uppercase tracking-wider text-[10px]">
              <th className="py-3 px-4">Payment ID</th>
              <th className="py-3 px-4">Amount</th>
              <th className="py-3 px-4">Gateway</th>
              <th className="py-3 px-4">Merchant DB</th>
              <th className="py-3 px-4">Diagnosed Problem</th>
              <th className="py-3 px-4">AI Policy</th>
              <th className="py-3 px-4">Current Status</th>
              <th className="py-3 px-4 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={8} className="py-8 text-center text-slate-400">
                  No payment incidents match the active filter criteria.
                </td>
              </tr>
            ) : (
              filtered.map((item) => {
                const isSelected = selectedId === item.id
                const badge = getStatusBadge(item)
                const BadgeIcon = badge.icon
                const isPay001 = item.id === 'pay_001'
                const isPay002 = item.id === 'pay_002'
                const isPay003 = item.id === 'pay_003'
                const isPay004 = item.id === 'pay_004'
                const isPay005 = item.id === 'pay_005'
                const rawState = String(item.recoveryStatus || item.status || 'PENDING').toUpperCase()
                const isRecovered = (rawState === 'SUCCESS' || rawState === 'RECOVERED') && (item.id !== 'pay_005' || item.status === 'RECOVERED')
                const isTerminal = isRecovered || isPay001 || isPay003 || isPay004 || rawState === 'STOPPED'

                return (
                  <tr
                    key={item.id}
                    onClick={() => onSelect(item.id)}
                    className={`hover:bg-slate-50/80 transition-colors cursor-pointer ${
                      isSelected ? 'bg-brand-50/50 font-medium' : ''
                    }`}
                  >
                    {/* Payment ID (Monospace font restricted to IDs) */}
                    <td className="py-3 px-4">
                      <span className="font-mono text-xs font-bold text-brand-700 bg-brand-50 px-2.5 py-1 rounded-md border border-brand-200/80">
                        {item.id}
                      </span>
                    </td>

                    {/* Amount (Standard Sans-Serif Typography) */}
                    <td className="py-3 px-4 font-bold text-slate-900">
                      ₹{item.amount.toLocaleString('en-IN')}
                    </td>

                    {/* Gateway Status */}
                    <td className="py-3 px-4">
                      <span className="inline-flex items-center gap-1 text-emerald-800 font-semibold text-[11px]">
                        <CheckCircle2 size={12} className="text-emerald-600" />
                        Captured
                      </span>
                    </td>

                    {/* Merchant DB Status */}
                    <td className="py-3 px-4">
                      {isRecovered ? (
                        <span className="inline-flex items-center gap-1 text-emerald-800 font-semibold text-[11px]">
                          <CheckCircle2 size={12} className="text-emerald-600" />
                          Created
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-amber-800 font-semibold text-[11px]">
                          <AlertTriangle size={12} className="text-amber-600" />
                          Missing
                        </span>
                      )}
                    </td>

                    {/* Diagnosed Problem */}
                    <td className="py-3 px-4 text-slate-600 max-w-[220px] truncate">
                      {isPay003 ? 'Merchant server error (500) during processing' : item.rootCause || 'Webhook timeout'}
                    </td>

                    {/* AI Policy / Original Recommendation */}
                    <td className="py-3 px-4">
                      {isPay001 ? (
                        <div className="space-y-0.5">
                          <span className="font-semibold text-slate-800 text-[11px]">AUTO RECOVERY</span>
                          <div className="text-[10px] text-slate-500 font-medium">Superseded by safety stop</div>
                        </div>
                      ) : isPay003 ? (
                        <span className="font-semibold text-slate-800 text-[11px]">STOP</span>
                      ) : isPay002 || isPay005 ? (
                        <span className="font-semibold text-slate-800 text-[11px]">HUMAN REVIEW</span>
                      ) : (
                        <span className="font-semibold text-slate-800 text-[11px]">
                          {item.decision || 'AUTO RECOVERY'}
                        </span>
                      )}
                    </td>

                    {/* Current Status Badge */}
                    <td className="py-3 px-4">
                      <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold border ${badge.className}`}>
                        <BadgeIcon size={11} />
                        <span>{badge.label}</span>
                      </span>
                    </td>

                    {/* Action */}
                    <td className="py-3 px-4 text-right">
                      {isTerminal ? (
                        <span className="text-[11px] text-slate-400 font-medium">Terminal State</span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-xs font-bold text-brand-600 hover:text-brand-700">
                          Review <ChevronRight size={13} />
                        </span>
                      )}
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
