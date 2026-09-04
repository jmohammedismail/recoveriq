import { AlertTriangle, ChevronRight, ShieldCheck, Clock, CheckCircle2 } from 'lucide-react'

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
