import { ShieldCheck, CheckCircle2 } from 'lucide-react'

const guardrails = [
  {
    id: 1,
    label: 'Maximum Retry Limit',
    detail: '2 retries before automatic escalation',
  },
  {
    id: 2,
    label: 'Merchant State Probing',
    detail: 'Order presence verified before recovery',
  },
  {
    id: 3,
    label: 'Idempotency Protection',
    detail: 'Unique deterministic payment-order key',
  },
  {
    id: 4,
    label: 'Post-Recovery Verification',
    detail: 'Order presence confirmed in merchant DB',
  },
  {
    id: 5,
    label: 'Human Review Threshold',
    detail: 'Confidence < 85% routed to manual queue',
  },
  {
    id: 6,
    label: 'Emergency Circuit Breaker',
    detail: 'Confidence < 50% triggers immediate halt',
  },
]

export default function SafetyGuardrails() {
  return (
    <div className="panel">
      <div className="panel-header">
        <div className="flex items-center gap-2">
          <ShieldCheck size={16} className="text-brand-600" />
          <span className="text-xs font-bold text-slate-800 uppercase tracking-wider">Safety Guardrails</span>
        </div>
        <span className="badge badge-green font-mono">6/6 ENFORCED</span>
      </div>
      <div className="p-4 grid grid-cols-1 sm:grid-cols-2 gap-2.5">
        {guardrails.map((g) => (
          <div
            key={g.id}
            className="flex items-start gap-2.5 p-2.5 rounded-lg bg-slate-50/80 border border-slate-200/70 hover:border-slate-300 transition-colors"
          >
            <div className="flex-shrink-0 mt-0.5 w-4 h-4 rounded-full bg-emerald-100 flex items-center justify-center">
              <CheckCircle2 size={12} className="text-emerald-600" />
            </div>
            <div>
              <div className="text-xs font-semibold text-slate-800 leading-tight">{g.label}</div>
              <div className="text-[11px] text-slate-500 mt-0.5">{g.detail}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
