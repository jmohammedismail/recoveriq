import { ChevronRight } from 'lucide-react'

const decisionBadge = {
  'AUTO RECOVERY': 'badge-green',
  'HUMAN REVIEW': 'badge-amber',
  'STOP': 'badge-red',
}

const statusBadge = {
  'SUCCESS': 'badge-green',
  'STOPPED': 'badge-orange',
  'PENDING': 'badge-amber',
  'ESCALATED': 'badge-red',
  'NOT_EXECUTED': 'badge-slate',
}

function ConfidenceBar({ value }) {
  const color = value >= 85 ? '#059669' : value >= 50 ? '#d97706' : '#dc2626'
  const bg = value >= 85 ? 'bg-emerald-500' : value >= 50 ? 'bg-amber-500' : 'bg-rose-500'

  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full bg-slate-200 overflow-hidden" style={{ maxWidth: 55 }}>
        <div
          className={`h-full rounded-full transition-all duration-500 ${bg}`}
          style={{ width: `${value}%` }}
        />
      </div>
      <span className="font-mono text-xs font-bold" style={{ color }}>{value}%</span>
    </div>
  )
}

export default function IncidentRow({ incident, selected, onClick }) {
  const webhookLabel = `${incident.webhookStatus} / ${incident.httpStatus}`

  return (
    <div
      onClick={onClick}
      className={`incident-row grid px-5 py-3.5 items-center cursor-pointer ${selected ? 'selected' : ''}`}
      style={{ gridTemplateColumns: '11% 10% 13% 23% 13% 12% 9% 9%' }}
    >
      {/* Payment ID */}
      <div className="flex items-center gap-1.5">
        <span className="font-mono text-xs font-bold text-brand-600 hover:text-brand-700">{incident.id}</span>
        {selected && <ChevronRight size={12} className="text-brand-600" />}
      </div>

      {/* Amount */}
      <div className="font-bold text-xs text-navy-900">
        ₹{incident.amount.toLocaleString('en-IN')}
      </div>

      {/* Webhook Status */}
      <div className={`font-mono text-xs font-medium ${incident.httpStatus === 504 ? 'text-amber-600' : 'text-rose-600'}`}>
        {webhookLabel}
      </div>

      {/* Root Cause */}
      <div className="text-xs text-slate-600 leading-tight truncate pr-3">
        {incident.rootCause}
      </div>

      {/* Confidence */}
      <div>
        <ConfidenceBar value={incident.confidence} />
      </div>

      {/* Decision */}
      <div>
        <span className={`badge ${decisionBadge[incident.decision] || 'badge-slate'}`}>
          {incident.decision}
        </span>
      </div>

      {/* Recovered */}
      <div className="text-xs">
        {incident.revenueRecovered > 0 ? (
          <span className="text-emerald-700 font-bold">
            ₹{incident.revenueRecovered.toLocaleString('en-IN')}
          </span>
        ) : (
          <span className="text-slate-600 font-mono">—</span>
        )}
      </div>

      {/* Status */}
      <div>
        <span className={`badge ${statusBadge[incident.recoveryStatus] || 'badge-slate'}`}>
          {incident.recoveryStatus}
        </span>
      </div>
    </div>
  )
}
