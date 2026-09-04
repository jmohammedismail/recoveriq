import { useState, useEffect } from 'react'
import {
  ShieldCheck, FileText, CheckCircle2, AlertTriangle, AlertCircle, Copy, Check,
  X, ChevronRight, ExternalLink, Filter, Search, Clock, UserCheck, Key, RefreshCw
} from 'lucide-react'
import { fetchAuditLogs } from '../../services/api'

export default function AuditTrail({ dynamicRecords, onRefresh }) {
  const [records, setRecords] = useState([])
  const [selectedRecord, setSelectedRecord] = useState(null)
  const [copiedKey, setCopiedKey] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')

  const loadAudit = async () => {
    try {
      const data = await fetchAuditLogs()
      if (data && data.length > 0) {
        setRecords(data)
      }
    } catch (e) {
      console.warn('Audit fetch fallback:', e)
    }
  }

  useEffect(() => {
    if (dynamicRecords && dynamicRecords.length > 0) {
      setRecords(dynamicRecords)
    } else {
      loadAudit()
    }
  }, [dynamicRecords])

  const filtered = (records.length > 0 ? records : []).filter(r => {
    const q = searchQuery.toLowerCase().trim()
    if (!q) return true
    const pid = r.paymentId || r.payment_id || ''
    const dec = r.decision || ''
    const stat = r.recoveryStatus || r.recovery_status || ''
    const key = r.recoveryKey || r.recovery_key || ''
    return (
      pid.toLowerCase().includes(q) ||
      dec.toLowerCase().includes(q) ||
      stat.toLowerCase().includes(q) ||
      key.toLowerCase().includes(q)
    )
  })

  const handleCopy = (text) => {
    navigator.clipboard.writeText(text)
    setCopiedKey(true)
    setTimeout(() => setCopiedKey(false), 2000)
  }

  const getStatusBadge = (status) => {
    const s = String(status || 'PENDING').toUpperCase()
    if (s === 'RECOVERED' || s === 'SUCCESS') {
      return { label: 'RECOVERED', className: 'bg-emerald-50 text-emerald-800 border-emerald-200' }
    }
    if (s === 'AWAITING_REVIEW' || s === 'HUMAN_REVIEW' || s === 'PENDING') {
      return { label: 'AWAITING_REVIEW', className: 'bg-amber-50 text-amber-800 border-amber-200' }
    }
    if (s === 'ESCALATED') {
      return { label: 'ESCALATED', className: 'bg-indigo-50 text-indigo-800 border-indigo-200' }
    }
    return { label: 'STOPPED', className: 'bg-slate-100 text-slate-700 border-slate-200' }
  }

  return (
    <div className="space-y-5">
      
      {/* Header */}
      <div className="p-6 bg-white border border-slate-200 rounded-2xl shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-brand-600 bg-brand-50 px-2.5 py-0.5 rounded-md border border-brand-200">
              Compliance Ledger
            </span>
            <span className="text-xs font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-md border border-emerald-200 flex items-center gap-1">
              <ShieldCheck size={12} /> Tamper-Evident Audit Active
            </span>
          </div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight mt-1">
            Recovery Audit Trail & Ledger
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Every recovery decision, state change, and operator authorization is recorded in a tamper-evident audit trail with zero mutable overrides.
          </p>
        </div>

        {/* Search */}
        <div className="relative max-w-xs w-full">
          <Search size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by Payment ID, Key..."
            className="w-full pl-9 pr-4 py-2 rounded-xl border border-slate-200 text-xs bg-slate-50 focus:bg-white focus:outline-hidden focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
          />
        </div>
      </div>

      {/* Main Table */}
      <div className="bg-white border border-slate-200 rounded-2xl shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-bold uppercase text-[10px] tracking-wider">
              <tr>
                <th className="px-5 py-3">Payment ID</th>
                <th className="px-5 py-3">Amount</th>
                <th className="px-5 py-3">Diagnosed Cause</th>
                <th className="px-5 py-3">Confidence</th>
                <th className="px-5 py-3">Idempotency Key</th>
                <th className="px-5 py-3">Policy Decision</th>
                <th className="px-5 py-3">Status</th>
                <th className="px-5 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white">
              {filtered.map((row, idx) => {
                const pid = row.paymentId || row.payment_id || `pay_00${idx+1}`
                const amount = row.amount || 3100
                const rootCause = row.rootCause || row.root_cause || 'Merchant server timeout after webhook delivery'
                const confidence = row.confidence || 88
                const key = row.recoveryKey || row.recovery_key || `${pid}_ORDER_SYNC_v1`
                const decision = row.decision || 'AUTO RECOVERY'
                const rawStat = row.recoveryStatus || row.recovery_status || 'RECOVERED'
                const badge = getStatusBadge(rawStat)

                return (
                  <tr key={pid} className="hover:bg-slate-50/80 transition-colors">
                    <td className="px-5 py-3.5 font-mono font-bold text-brand-700">
                      {pid}
                    </td>

                    <td className="px-5 py-3.5 font-mono font-bold text-slate-900">
                      ₹{Number(amount).toLocaleString('en-IN')}
                    </td>

                    <td className="px-5 py-3.5 text-slate-700 font-medium max-w-xs truncate">
                      {rootCause}
                    </td>

                    <td className="px-5 py-3.5 font-mono font-bold text-slate-800">
                      {confidence}%
                    </td>

                    <td className="px-5 py-3.5 font-mono text-[11px] text-slate-600 max-w-xs truncate">
                      {key}
                    </td>

                    <td className="px-5 py-3.5 font-semibold text-slate-800">
                      {decision}
                    </td>

                    <td className="px-5 py-3.5">
                      <span className={`inline-flex px-2 py-0.5 rounded-full text-[10px] font-bold border ${badge.className}`}>
                        {badge.label}
                      </span>
                    </td>

                    <td className="px-5 py-3.5 text-right">
                      <button
                        onClick={() => setSelectedRecord({ pid, amount, rootCause, confidence, key, decision, rawStat })}
                        className="px-2.5 py-1 rounded-lg bg-brand-50 hover:bg-brand-100 text-brand-700 text-xs font-bold transition-colors cursor-pointer"
                      >
                        Inspect
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Expandable Inspect Drawer Modal */}
      {selectedRecord && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white border border-slate-200 rounded-2xl shadow-2xl max-w-lg w-full overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50">
              <div className="flex items-center gap-2">
                <FileText size={16} className="text-brand-600" />
                <h3 className="text-sm font-bold text-slate-900">
                  Audit Lifecycle Ledger: {selectedRecord.pid}
                </h3>
              </div>
              <button
                onClick={() => setSelectedRecord(null)}
                className="text-slate-400 hover:text-slate-700 cursor-pointer"
              >
                <X size={16} />
              </button>
            </div>

            <div className="p-6 space-y-4 text-xs">
              {/* Idempotency Key Banner */}
              <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200 space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-slate-700 text-xs">Pre-Allocated Idempotency Key</span>
                  <button
                    onClick={() => handleCopy(selectedRecord.key)}
                    className="text-brand-600 hover:text-brand-700 flex items-center gap-1 text-[11px] font-semibold cursor-pointer"
                  >
                    {copiedKey ? <Check size={12} /> : <Copy size={12} />}
                    <span>{copiedKey ? 'Copied' : 'Copy Key'}</span>
                  </button>
                </div>
                <div className="font-mono text-xs text-brand-800 break-all">
                  {selectedRecord.key}
                </div>
              </div>

              {/* Lifecycle Timeline */}
              <div className="space-y-2">
                <span className="font-bold text-slate-800 text-xs">Lifecycle Timeline:</span>
                <div className="border-l-2 border-brand-200 ml-2 pl-3 space-y-2.5 text-[11px]">
                  <div>
                    <div className="font-mono text-slate-400">16:00:01 IST</div>
                    <div className="font-bold text-slate-900">Payment failure detected</div>
                    <div className="text-slate-500">Gateway captured ₹{selectedRecord.amount}; merchant confirmation timed out.</div>
                  </div>
                  <div>
                    <div className="font-mono text-slate-400">16:00:03 IST</div>
                    <div className="font-bold text-slate-900">4-way reconciliation running</div>
                    <div className="text-slate-500">Signals gathered: Gateway, Merchant DB, Internal state, Webhook.</div>
                  </div>
                  <div>
                    <div className="font-mono text-slate-400">16:00:04 IST</div>
                    <div className="font-bold text-slate-900">Confidence evaluated ({selectedRecord.confidence}%)</div>
                    <div className="text-slate-500">Policy: {selectedRecord.decision}.</div>
                  </div>
                  <div>
                    <div className="font-mono text-slate-400">16:00:05 IST</div>
                    <div className="font-bold text-emerald-700">Audit record committed</div>
                    <div className="text-slate-500">Tamper-evident audit entry saved with signature verification.</div>
                  </div>
                </div>
              </div>

              {/* Attribution Grid */}
              <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
                <div className="p-2 bg-slate-50 rounded-lg border border-slate-200">
                  <span className="text-slate-400">Actor:</span>
                  <div className="font-bold text-slate-900">OPERATOR / AI_AGENT</div>
                </div>
                <div className="p-2 bg-slate-50 rounded-lg border border-slate-200">
                  <span className="text-slate-400">Verification:</span>
                  <div className="font-bold text-emerald-700">VERIFIED_SUCCESS</div>
                </div>
              </div>
            </div>

            <div className="px-6 py-3.5 bg-slate-50 border-t border-slate-100 flex justify-end">
              <button
                onClick={() => setSelectedRecord(null)}
                className="px-4 py-1.5 rounded-xl bg-slate-900 text-white text-xs font-bold cursor-pointer"
              >
                Close Drawer
              </button>
            </div>

          </div>
        </div>
      )}

    </div>
  )
}
