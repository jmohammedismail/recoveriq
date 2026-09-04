import React, { useState, useEffect } from 'react'
import { 
  Zap, ShieldAlert, ShieldCheck, Clock, RefreshCw, 
  AlertTriangle, ChevronDown, ChevronUp, Activity, 
  Sliders, ArrowRight, UserCheck, X, CheckCircle2, Shield
} from 'lucide-react'
import { 
  fetchCircuitBreakerStatus, 
  fetchBlockedCircuitBreakerRequests, 
  fetchCircuitLifecycleEvents,
  fetchMerchantResilience,
  operatorForceOpenCircuit,
  operatorResetCircuit,
  operatorProbeCircuit
} from '../../services/api'

export default function CircuitBreakerCard({ merchantId = 'merchant_demo', endpoint = 'payment-webhook' }) {
  const [circuit, setCircuit] = useState(null)
  const [resilience, setResilience] = useState(null)
  const [blockedRequests, setBlockedRequests] = useState([])
  const [lifecycleEvents, setLifecycleEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showLifecycle, setShowLifecycle] = useState(false)
  const [showBlocked, setShowBlocked] = useState(false)

  // Topic 2.2.2.7 Operator Override Modal state
  const [activeModal, setActiveModal] = useState(null) // { action: 'FORCE_OPEN' | 'RESET' | 'MANUAL_PROBE', title, targetState, warning }
  const [overrideReason, setOverrideReason] = useState('')
  const [isSubmittingOverride, setIsSubmittingOverride] = useState(false)
  const [overrideFeedback, setOverrideFeedback] = useState(null)
  const [overrideError, setOverrideError] = useState(null)

  const loadData = async (isManual = false) => {
    if (isManual) setLoading(true)
    setError(null)
    try {
      const [resilienceRes, blockedRes, lifecycleRes] = await Promise.allSettled([
        fetchMerchantResilience(merchantId, endpoint),
        fetchBlockedCircuitBreakerRequests(merchantId),
        fetchCircuitLifecycleEvents(merchantId)
      ])

      if (resilienceRes.status === 'fulfilled' && resilienceRes.value?.circuit_breaker) {
        setCircuit(resilienceRes.value.circuit_breaker)
        setResilience(resilienceRes.value)
      } else if (resilienceRes.status === 'rejected') {
        // Fallback to standalone circuit status
        const fallbackStatus = await fetchCircuitBreakerStatus(merchantId, endpoint)
        if (fallbackStatus?.circuit_breaker) {
          setCircuit(fallbackStatus.circuit_breaker)
        }
      }

      if (blockedRes.status === 'fulfilled' && blockedRes.value?.blocked_requests) {
        setBlockedRequests(blockedRes.value.blocked_requests)
      }

      if (lifecycleRes.status === 'fulfilled' && lifecycleRes.value?.lifecycle_events) {
        setLifecycleEvents(lifecycleRes.value.lifecycle_events)
      }
    } catch (err) {
      setError(err?.message || 'Could not load circuit breaker status.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
    // Poll every 6 seconds for live cooldown / state transitions
    const timer = setInterval(() => {
      loadData(false)
    }, 6000)

    return () => clearInterval(timer)
  }, [merchantId, endpoint])

  const openOverrideModal = (actionKey) => {
    setOverrideReason('')
    setOverrideError(null)
    setOverrideFeedback(null)

    if (actionKey === 'FORCE_OPEN') {
      setActiveModal({
        action: 'FORCE_OPEN',
        title: 'Force Open Circuit',
        targetState: 'OPEN',
        warning: 'This will immediately halt all downstream merchant requests for this endpoint.',
        btnColor: 'bg-rose-600 hover:bg-rose-700 text-white'
      })
    } else if (actionKey === 'RESET') {
      setActiveModal({
        action: 'RESET',
        title: 'Reset Circuit to CLOSED',
        targetState: 'CLOSED',
        warning: 'This restores normal traffic flow. Ensure merchant endpoint health has been verified.',
        btnColor: 'bg-emerald-600 hover:bg-emerald-700 text-white'
      })
    } else if (actionKey === 'MANUAL_PROBE') {
      setActiveModal({
        action: 'MANUAL_PROBE',
        title: 'Request Recovery Probe',
        targetState: 'HALF_OPEN',
        warning: 'This transitions the circuit to HALF_OPEN to admit limited recovery probes.',
        btnColor: 'bg-amber-600 hover:bg-amber-700 text-white'
      })
    }
  }

  const handleConfirmOverride = async () => {
    if (!activeModal || !overrideReason.trim()) return
    setIsSubmittingOverride(true)
    setOverrideError(null)

    const idempotencyKey = `cb_${activeModal.action.toLowerCase()}_${merchantId}_${endpoint}_${Date.now()}`

    try {
      let res
      const payload = {
        endpoint,
        reason: overrideReason.trim(),
        operator_id: 'demo-operator',
        idempotency_key: idempotencyKey
      }

      if (activeModal.action === 'FORCE_OPEN') {
        res = await operatorForceOpenCircuit(merchantId, payload)
      } else if (activeModal.action === 'RESET') {
        res = await operatorResetCircuit(merchantId, payload)
      } else if (activeModal.action === 'MANUAL_PROBE') {
        res = await operatorProbeCircuit(merchantId, payload)
      }

      setActiveModal(null)
      setOverrideFeedback({
        action: activeModal.action,
        title: activeModal.title,
        message: res?.duplicate
          ? 'Circuit action already executed (idempotent response).'
          : (res?.message || 'Circuit override applied successfully.')
      })
      // Immediate reload of live status
      loadData(false)
    } catch (err) {
      setOverrideError(err?.message || 'Failed to execute circuit override.')
    } finally {
      setIsSubmittingOverride(false)
    }
  }

  if (loading && !circuit) {
    return (
      <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-500 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Zap size={14} className="text-brand-600 animate-pulse" />
          <span>Loading circuit breaker status...</span>
        </div>
      </div>
    )
  }

  if (error && !circuit) {
    return (
      <div className="p-3.5 rounded-xl bg-rose-50/60 border border-rose-200 text-xs text-rose-700 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <AlertTriangle size={14} />
          <span>{error}</span>
        </div>
        <button
          type="button"
          onClick={() => loadData(true)}
          className="text-[11px] font-bold text-rose-800 hover:underline flex items-center gap-1"
        >
          <RefreshCw size={11} /> Retry
        </button>
      </div>
    )
  }

  const state = circuit?.state || 'CLOSED'
  const isClosed = state === 'CLOSED'
  const isOpen = state === 'OPEN'
  const isHalfOpen = state === 'HALF_OPEN'

  const healthStatus = resilience?.merchant_health?.health || 'NO_DATA'
  const riskLevel = resilience?.resilience_summary?.risk_level || (isOpen ? 'CRITICAL' : isHalfOpen ? 'HIGH' : 'LOW')
  const explanation = circuit?.decision_explanation || resilience?.resilience_summary?.explanation || 
    (isClosed ? 'Circuit Closed — Merchant requests are allowed.' :
     isOpen ? 'Circuit Open — Downstream requests are temporarily blocked.' :
     'Circuit Half-Open — Cautious recovery probes in progress.')

  return (
    <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 space-y-2.5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Zap size={15} className={isClosed ? 'text-emerald-600' : isOpen ? 'text-rose-600' : 'text-amber-600'} />
          <span className="text-xs font-bold text-slate-800 tracking-tight">CIRCUIT BREAKER</span>
        </div>
        <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold tracking-wide ${
          isClosed ? 'bg-emerald-100 text-emerald-800 border border-emerald-200' :
          isOpen ? 'bg-rose-100 text-rose-800 border border-rose-200' :
          'bg-amber-100 text-amber-800 border border-amber-200'
        }`}>
          {isClosed ? '● CLOSED' : isOpen ? '● OPEN' : '● HALF-OPEN'}
        </span>
      </div>

      {/* State & Decision Explanation Banner (Topic 2.2.2.8) */}
      <div className={`p-2.5 rounded-lg border text-[11px] font-medium leading-tight ${
        isClosed ? 'bg-emerald-50/80 border-emerald-200/60 text-emerald-900' :
        isOpen ? 'bg-rose-50/80 border-rose-200/60 text-rose-900' :
        'bg-amber-50/80 border-amber-200/60 text-amber-900'
      }`}>
        {explanation}
      </div>

      {/* Combined Resilience Status Context (Topic 2.2.2.8) */}
      <div className="p-2 rounded-lg bg-white border border-slate-200 text-[10px] flex items-center justify-between text-slate-700">
        <div className="flex items-center gap-1.5 font-medium">
          <Activity size={12} className={
            healthStatus === 'HEALTHY' ? 'text-emerald-600' :
            healthStatus === 'DEGRADED' ? 'text-amber-600' :
            healthStatus === 'UNHEALTHY' ? 'text-rose-600' : 'text-slate-400'
          } />
          <span>Health: <strong>{healthStatus}</strong></span>
        </div>
        <div className="flex items-center gap-1.5">
          <Shield size={12} className={
            riskLevel === 'CRITICAL' ? 'text-rose-600' :
            riskLevel === 'HIGH' ? 'text-amber-600' :
            riskLevel === 'ELEVATED' ? 'text-blue-600' : 'text-emerald-600'
          } />
          <span>Risk: <strong className={
            riskLevel === 'CRITICAL' ? 'text-rose-700' :
            riskLevel === 'HIGH' ? 'text-amber-700' :
            riskLevel === 'ELEVATED' ? 'text-blue-700' : 'text-emerald-700'
          }>{riskLevel}</strong></span>
        </div>
        <div className="font-mono font-bold">
          Requests: <span className={isClosed || (isHalfOpen && circuit?.half_open_probe_count < circuit?.half_open_probe_limit) ? 'text-emerald-700' : 'text-rose-700'}>
            {isClosed ? 'ALLOWED' : isHalfOpen ? 'PROBING' : 'BLOCKED'}
          </span>
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-4 gap-1.5 text-center text-[10px]">
        <div className="p-2 rounded-lg bg-white border border-slate-200">
          <span className="text-slate-400 block font-semibold">Failures</span>
          <span className="font-bold font-mono text-slate-800 text-xs">
            {circuit?.consecutive_failures || 0} / {circuit?.failure_threshold || 5}
          </span>
        </div>
        <div className="p-2 rounded-lg bg-white border border-slate-200">
          <span className="text-slate-400 block font-semibold">Total Fails</span>
          <span className="font-bold font-mono text-slate-800 text-xs">
            {circuit?.total_failures || 0}
          </span>
        </div>
        <div className="p-2 rounded-lg bg-white border border-slate-200">
          <span className="text-slate-400 block font-semibold">{isOpen ? 'Cooldown' : isHalfOpen ? 'Probes' : 'Cooldown'}</span>
          <span className={`font-bold font-mono text-xs ${isOpen && circuit?.cooldown_remaining_sec > 0 ? 'text-rose-700' : 'text-slate-800'}`}>
            {isOpen ? `${circuit?.cooldown_remaining_sec || 0}s` :
             isHalfOpen ? `${circuit?.half_open_probe_count || 0} / ${circuit?.half_open_probe_limit || 3}` :
             `${circuit?.cooldown_duration_sec || 30}s`}
          </span>
        </div>
        <div className="p-2 rounded-lg bg-white border border-slate-200">
          <span className="text-slate-400 block font-semibold">Gen / Status</span>
          <span className="font-bold font-mono text-slate-800 text-xs">
            v{circuit?.circuit_generation || 0}
          </span>
        </div>
      </div>

      {/* Detail Footer */}
      <div className="flex items-center justify-between text-[11px] text-slate-600 pt-0.5">
        <span>
          {isOpen && circuit?.last_failure_category ? (
            <>Last: <strong>{circuit.last_failure_category}</strong></>
          ) : (
            <>Persistence: <strong className="text-emerald-700">{circuit?.persistence?.status || 'PERSISTED'}</strong></>
          )}
        </span>

        <div className="flex items-center gap-3">
          {blockedRequests.length > 0 && (
            <button
              type="button"
              onClick={() => setShowBlocked(prev => !prev)}
              className="text-[10px] font-mono text-rose-600 hover:text-rose-800 font-semibold"
            >
              {showBlocked ? 'Hide Blocked' : `Blocked (${blockedRequests.length})`}
            </button>
          )}

          <button
            type="button"
            onClick={() => setShowLifecycle(prev => !prev)}
            className="text-[10px] font-mono text-brand-600 hover:text-brand-800 font-semibold"
          >
            {showLifecycle ? 'Hide Lifecycle' : 'Lifecycle Events'}
          </button>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* TOPIC 2.2.2.7 — CONTROLLED OPERATOR CIRCUIT OVERRIDES SECTION */}
      {/* ========================================================================= */}
      <div className="pt-2 border-t border-slate-200/80 space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1">
            <Sliders size={11} /> Circuit Operator Controls
          </span>
          <span className="text-[9px] font-mono text-slate-400">Human Override</span>
        </div>

        {/* Action Buttons depending on current state */}
        <div className="flex items-center gap-2">
          {isClosed && (
            <button
              type="button"
              onClick={() => openOverrideModal('FORCE_OPEN')}
              className="flex-1 py-1.5 px-3 rounded-lg bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 text-xs font-bold transition-all flex items-center justify-center gap-1.5"
            >
              <ShieldAlert size={12} /> Force Open
            </button>
          )}

          {isOpen && (
            <>
              <button
                type="button"
                onClick={() => openOverrideModal('RESET')}
                className="flex-1 py-1.5 px-3 rounded-lg bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-200 text-xs font-bold transition-all flex items-center justify-center gap-1.5"
              >
                <ShieldCheck size={12} /> Reset Circuit
              </button>
              <button
                type="button"
                onClick={() => openOverrideModal('MANUAL_PROBE')}
                className="flex-1 py-1.5 px-3 rounded-lg bg-amber-50 hover:bg-amber-100 text-amber-700 border border-amber-200 text-xs font-bold transition-all flex items-center justify-center gap-1.5"
              >
                <Zap size={12} /> Request Probe
              </button>
            </>
          )}

          {isHalfOpen && (
            <>
              <button
                type="button"
                onClick={() => openOverrideModal('FORCE_OPEN')}
                className="flex-1 py-1.5 px-3 rounded-lg bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 text-xs font-bold transition-all flex items-center justify-center gap-1.5"
              >
                <ShieldAlert size={12} /> Force Open
              </button>
              <button
                type="button"
                onClick={() => openOverrideModal('RESET')}
                className="flex-1 py-1.5 px-3 rounded-lg bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-200 text-xs font-bold transition-all flex items-center justify-center gap-1.5"
              >
                <ShieldCheck size={12} /> Close Circuit
              </button>
            </>
          )}
        </div>

        {/* Feedback Banner */}
        {overrideFeedback && (
          <div className="p-2 rounded-lg bg-emerald-50 border border-emerald-200 text-[11px] text-emerald-800 flex items-center justify-between animate-fadeIn">
            <div className="flex items-center gap-1.5">
              <CheckCircle2 size={13} className="text-emerald-600" />
              <span>{overrideFeedback.message}</span>
            </div>
            <button
              type="button"
              onClick={() => setOverrideFeedback(null)}
              className="text-emerald-700 hover:text-emerald-900"
            >
              <X size={12} />
            </button>
          </div>
        )}
      </div>

      {/* Blocked Requests Section */}
      {showBlocked && blockedRequests.length > 0 && (
        <div className="p-2.5 bg-rose-50/60 rounded-lg border border-rose-200 text-[10px] font-mono text-rose-900 space-y-1.5 animate-fadeIn">
          <div className="font-bold text-rose-800 pb-1 border-b border-rose-200">Recent Blocked Requests (Fast-Fail):</div>
          {blockedRequests.slice(-3).reverse().map((b, i) => (
            <div key={b.event_id || i} className="flex items-center justify-between py-0.5">
              <span className="font-bold text-rose-700">{b.reason || 'CIRCUIT_OPEN'}</span>
              <span>{b.payment_id || b.endpoint}</span>
              <span className="text-slate-400">{b.timestamp ? new Date(b.timestamp).toLocaleTimeString() : 'now'}</span>
            </div>
          ))}
        </div>
      )}

      {/* Collapsible Lifecycle Timeline */}
      {showLifecycle && (
        <div className="p-2.5 bg-white rounded-lg border border-slate-200 text-[10px] font-mono text-slate-600 space-y-1.5 animate-fadeIn">
          <div className="font-bold text-slate-700 pb-1 border-b border-slate-100">Circuit Lifecycle Timeline:</div>
          {lifecycleEvents.length > 0 ? (
            lifecycleEvents.slice(-4).reverse().map((evt, i) => (
              <div key={evt.event_id || i} className="space-y-0.5 py-1 border-b border-slate-50 last:border-none">
                <div className="flex items-center justify-between">
                  <span className={`font-bold ${
                    evt.event_type?.includes('OVERRIDE') ? 'text-purple-700' :
                    evt.event_type?.includes('OPEN') ? 'text-rose-700' :
                    evt.event_type?.includes('CLOSED') ? 'text-emerald-700' :
                    'text-amber-700'
                  }`}>
                    {evt.event_type} {evt.actor_type === 'OPERATOR' && '(OPERATOR)'}
                  </span>
                  <span className="text-slate-400">{evt.timestamp ? new Date(evt.timestamp).toLocaleTimeString() : 'now'}</span>
                </div>
                <div className="text-[9px] text-slate-500 truncate">{evt.reason}</div>
              </div>
            ))
          ) : (
            <div className="text-[10px] text-slate-400 py-1">No lifecycle transitions recorded yet.</div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* OPERATOR OVERRIDE CONFIRMATION MODAL */}
      {/* ========================================================================= */}
      {activeModal && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-fadeIn">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xl max-w-md w-full p-5 space-y-4 animate-scaleUp">
            
            {/* Modal Header */}
            <div className="flex items-center justify-between pb-2 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <Sliders size={16} className="text-brand-600" />
                <span className="font-bold text-sm text-slate-900">{activeModal.title}</span>
              </div>
              <button
                type="button"
                onClick={() => setActiveModal(null)}
                className="w-7 h-7 rounded-lg flex items-center justify-center text-slate-400 hover:text-slate-700 hover:bg-slate-100"
              >
                <X size={14} />
              </button>
            </div>

            {/* Target Transition & Warning */}
            <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-slate-500 font-semibold">Transition:</span>
                <div className="flex items-center gap-1.5 font-bold font-mono">
                  <span className="px-2 py-0.5 bg-slate-200 text-slate-800 rounded">{state}</span>
                  <ArrowRight size={12} className="text-slate-400" />
                  <span className={`px-2 py-0.5 rounded ${
                    activeModal.targetState === 'OPEN' ? 'bg-rose-100 text-rose-800' :
                    activeModal.targetState === 'CLOSED' ? 'bg-emerald-100 text-emerald-800' :
                    'bg-amber-100 text-amber-800'
                  }`}>
                    {activeModal.targetState}
                  </span>
                </div>
              </div>

              <div className="flex items-center justify-between text-[11px]">
                <span className="text-slate-500 font-semibold">Target Endpoint:</span>
                <span className="font-mono text-slate-800">{merchantId} / {endpoint}</span>
              </div>

              <div className="flex items-center justify-between text-[11px]">
                <span className="text-slate-500 font-semibold">Actor Identity:</span>
                <span className="inline-flex items-center gap-1 text-slate-700 font-semibold">
                  <UserCheck size={12} className="text-brand-600" /> OPERATOR · demo-operator
                </span>
              </div>

              <p className="text-[11px] text-slate-600 pt-1 border-t border-slate-200">
                {activeModal.warning}
              </p>
            </div>

            {/* Reason Textarea (Mandatory) */}
            <div className="space-y-1.5">
              <label className="block text-xs font-bold text-slate-700">
                Mandatory Reason <span className="text-rose-500">*</span>
              </label>
              <textarea
                rows={2}
                value={overrideReason}
                onChange={(e) => setOverrideReason(e.target.value)}
                placeholder="Enter operational reason for this override..."
                className="w-full text-xs p-2.5 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
              />
              <span className="text-[10px] text-slate-400 block">
                Every operator override is audited and recorded to the circuit lifecycle log.
              </span>
            </div>

            {/* Error in modal */}
            {overrideError && (
              <div className="p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-700 flex items-center gap-2">
                <AlertTriangle size={14} className="shrink-0" />
                <span>{overrideError}</span>
              </div>
            )}

            {/* Actions */}
            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setActiveModal(null)}
                disabled={isSubmittingOverride}
                className="px-3.5 py-1.5 rounded-lg text-xs font-semibold text-slate-600 hover:bg-slate-100 transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmOverride}
                disabled={isSubmittingOverride || !overrideReason.trim()}
                className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all shadow-xs flex items-center gap-1.5 ${activeModal.btnColor} disabled:opacity-40 disabled:cursor-not-allowed`}
              >
                {isSubmittingOverride ? (
                  <>
                    <RefreshCw size={12} className="animate-spin" />
                    <span>Applying...</span>
                  </>
                ) : (
                  <span>Confirm {activeModal.title}</span>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
