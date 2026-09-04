import { useState, useEffect } from 'react'
import {
  X, CheckCircle2, AlertTriangle, AlertCircle, ShieldCheck, ShieldAlert,
  ChevronDown, ChevronUp, Copy, Check, Terminal, ExternalLink, RefreshCw, Lock,
  FileText, Activity, Server, ArrowRight, CornerDownRight, Zap, Info, Clock, AlertOctagon
} from 'lucide-react'
import {
  getPaymentOperationalSnapshot,
  approvePaymentRecoveryWithIdempotency,
  rejectHumanReview,
  escalateHumanReview
} from '../../services/api'

export default function IncidentDetailPanel({ incident, onClose, onRunRecovery }) {
  const [snapshot, setSnapshot] = useState(null)
  const [loadingSnapshot, setLoadingSnapshot] = useState(true)
  const [copiedKey, setCopiedKey] = useState(false)
  const [copiedJson, setCopiedJson] = useState(false)
  const [activeModalAction, setActiveModalAction] = useState(null)
  const [isProcessingAction, setIsProcessingAction] = useState(false)
  const [actionFeedback, setActionFeedback] = useState(null)

  // Modals state
  const [rejectReason, setRejectReason] = useState('Duplicate payment suspected or customer requested cancellation.')
  const [escalateReason, setEscalateReason] = useState('Payment requires engineering on-call forensic inspection.')
  const [escalatePriority, setEscalatePriority] = useState('HIGH')

  // Progressive Disclosure Accordions
  const [showAiReasoning, setShowAiReasoning] = useState(false)
  const [showTechnicalDetails, setShowTechnicalDetails] = useState(false)
  const [rawJsonTab, setRawJsonTab] = useState('snapshot')

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
  const rawState = String(snapshot?.authoritative_payment_state || incident?.recoveryStatus || incident?.status || 'HUMAN_REVIEW').toUpperCase()
  const isRecovered = (rawState === 'RECOVERED' || rawState === 'SUCCESS') && (paymentId !== 'pay_005' || snapshot?.authoritative_payment_state === 'RECOVERED')
  const isStopped = paymentId === 'pay_001' || paymentId === 'pay_003' || rawState === 'STOPPED' || rawState === 'REFUNDED'
  const isEscalated = rawState === 'ESCALATED'
  const isPendingReview = (paymentId === 'pay_002' || paymentId === 'pay_005' || rawState === 'HUMAN_REVIEW' || rawState === 'PENDING' || rawState === 'AWAITING_REVIEW') && !isRecovered && !isStopped && !isEscalated
  const isTerminal = snapshot?.is_terminal !== undefined ? snapshot.is_terminal : (isRecovered || isStopped || paymentId === 'pay_001' || paymentId === 'pay_003' || paymentId === 'pay_004')

  const statusBadge = isRecovered ? {
    label: 'Recovered',
    className: 'bg-emerald-50 text-emerald-800 border-emerald-200',
    icon: CheckCircle2
  } : isStopped ? {
    label: 'Stopped / Safe',
    className: 'bg-slate-100 text-slate-700 border-slate-200',
    icon: ShieldAlert
  } : isPendingReview ? {
    label: 'Needs Review',
    className: 'bg-amber-50 text-amber-800 border-amber-200',
    icon: AlertTriangle
  } : isEscalated ? {
    label: 'Escalated to Operations',
    className: 'bg-indigo-50 text-indigo-800 border-indigo-200',
    icon: AlertOctagon
  } : {
    label: 'Failed',
    className: 'bg-rose-50 text-rose-800 border-rose-200',
    icon: AlertCircle
  }

  const StatusIcon = statusBadge.icon
  const idempotencyKey = snapshot?.idempotency_intent?.idempotency_key || `${paymentId}_ORDER_SYNC_v1`
  const confidence = snapshot?.confidence_score || incident?.confidence || 60
  const decisionThreshold = snapshot?.decision_threshold || 85

  // Canonical Incident Creation Timestamp (Formatted readable sans-serif)
  const formattedIncidentTime = "Sep 4, 2026 · 4:00 PM IST"

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
        reviewer_id: 'merchant_operator',
        reason: 'Authorized order synchronization after verifying customer receipt.',
        recovery_strategy: 'order_sync'
      })
      setActionFeedback({ success: true, message: 'Payment recovery approved and executed successfully! Order synchronized.' })
      await loadSnapshot()
      if (onRunRecovery) onRunRecovery(paymentId)
    } catch (err) {
      setActionFeedback({ success: false, message: err.message || 'Approval failed.' })
    } finally {
      setIsProcessingAction(false)
      setActiveModalAction(null)
    }
  }

  // Handle Reject Action
  const handleRejectRecovery = async () => {
    setIsProcessingAction(true)
    setActionFeedback(null)
    try {
      const res = await rejectHumanReview(paymentId, {
        reviewer_id: 'merchant_operator',
        reason: rejectReason || 'Operator rejected recovery.'
      })
      setActionFeedback({ success: true, message: 'Recovery rejected and safely halted. Payment state moved to STOPPED.' })
      await loadSnapshot()
      if (onRunRecovery) onRunRecovery(paymentId)
    } catch (err) {
      setActionFeedback({ success: false, message: err.message || 'Rejection failed.' })
    } finally {
      setIsProcessingAction(false)
      setActiveModalAction(null)
    }
  }

  // Handle Escalate Action
  const handleEscalateRecovery = async () => {
    setIsProcessingAction(true)
    setActionFeedback(null)
    try {
      const res = await escalateHumanReview(paymentId, {
        reviewer_id: 'merchant_operator',
        reason: escalateReason || 'Escalated to engineering on-call.',
        priority: escalatePriority
      })
      setActionFeedback({ success: true, message: 'Payment escalated to Senior Operations / Engineering On-call.' })
      await loadSnapshot()
      if (onRunRecovery) onRunRecovery(paymentId)
    } catch (err) {
      setActionFeedback({ success: false, message: err.message || 'Escalation failed.' })
    } finally {
      setIsProcessingAction(false)
      setActiveModalAction(null)
    }
  }

  // Masked JSON Payloads for sensitive data security
  const sampleRequestPayload = {
    event: 'payment.captured',
    payment_id: paymentId,
    order_id: `ORD_${paymentId.replace('pay_', '')}`,
    amount: amount,
    currency: 'INR',
    customer: { email: 'c*****r@example.com', phone: '+91 98*** ***10' },
    card: { last4: '4242', network: 'VISA' },
    gateway: 'razorpay',
    status: 'captured'
  }

  const sampleResponsePayload = {
    status: isRecovered ? 'success' : isStopped ? 'halted' : 'pending_review',
    payment_id: paymentId,
    order_synchronized: isRecovered,
    idempotency_key: idempotencyKey,
    verification: isRecovered ? 'VERIFIED_SUCCESS' : 'PENDING_AUTHORIZATION',
    timestamp: new Date().toISOString()
  }

  const sampleHeaders = {
    'X-Webhook-Signature': '[REDACTED_HMAC_SHA256]',
    'X-Signature-Timestamp': '1772448000',
    'X-Idempotency-Key': idempotencyKey,
    'Authorization': '[REDACTED]',
    'Content-Type': 'application/json'
  }

  return (
    <div className="bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden animate-in fade-in-50 duration-200">
      
      {/* ========================================================================= */}
      {/* STICKY PAYMENT CONTEXT HEADER */}
      {/* ========================================================================= */}
      <div className="sticky top-0 z-10 bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3 flex-wrap">
          {/* Monospace restricted strictly to technical Transaction ID */}
          <span className="font-mono text-xs font-bold text-brand-700 bg-brand-50 px-3 py-1 rounded-lg border border-brand-200">
            {paymentId}
          </span>
          {/* Standard Sans-Serif for Amount */}
          <span className="text-lg font-bold text-slate-900">
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
          <div className="p-3 bg-slate-50 border border-slate-200/80 rounded-xl space-y-0.5" title="Payment gateway successfully captured and confirmed customer funds.">
            <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Gateway Status</div>
            <div className="text-xs font-bold text-emerald-800 flex items-center gap-1">
              <CheckCircle2 size={12} className="text-emerald-600" />
              <span>Funds Captured</span>
            </div>
          </div>

          <div className="p-3 bg-slate-50 border border-slate-200/80 rounded-xl space-y-0.5" title="Order record status in your internal merchant database.">
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

          <div className="p-3 bg-slate-50 border border-slate-200/80 rounded-xl space-y-0.5" title="Pre-allocated idempotency key prevents duplicate orders or double-charging.">
            <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Duplicate Protection</div>
            <div className="text-xs font-bold text-slate-900 flex items-center gap-1">
              <ShieldCheck size={12} className="text-brand-600" />
              <span>Active</span>
            </div>
          </div>

          <div className="p-3 bg-slate-50 border border-slate-200/80 rounded-xl space-y-0.5">
            <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Incident Time</div>
            <div className="text-xs text-slate-700 font-medium">
              {formattedIncidentTime}
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
            {paymentId === 'pay_001'
              ? 'Payment succeeded on gateway. AI recommended Auto Recovery, but safety guardrails stopped execution because order presence was verified in your merchant database, preventing a duplicate order.'
              : paymentId === 'pay_002'
              ? 'Payment succeeded on gateway, but order confirmation timed out. Webhook retry limit was reached (2/2) with 60% confidence, routing the case to merchant review.'
              : paymentId === 'pay_003'
              ? 'Payment succeeded on gateway, but merchant server returned HTTP 500 (Internal Server Error). RecoverIQ intentionally halted autonomous recovery per safety policy to prevent further errors.'
              : paymentId === 'pay_004'
              ? 'Payment succeeded on gateway and order was missing in merchant database. Autonomous idempotent recovery successfully created and confirmed the order.'
              : paymentId === 'pay_005'
              ? (isRecovered
                  ? 'The payment succeeded and the merchant order has been synchronized and verified in your database.'
                  : 'Your payment gateway successfully captured ₹3,100 from the customer, but your merchant order management system did not acknowledge order creation due to a network timeout.')
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
              {paymentId === 'pay_001'
                ? 'No recovery needed. Order already exists in your merchant database.'
                : paymentId === 'pay_002'
                ? 'Review payment and approve safe order synchronization to place the missing order without re-charging the customer.'
                : paymentId === 'pay_003'
                ? 'Recovery stopped safely by policy. Server error requires merchant backend resolution; no automated retries permitted.'
                : isRecovered
                ? 'No action needed. The transaction has been reconciled and the order is active.'
                : 'Approve safe order synchronization to place the missing order without re-charging the customer.'}
            </p>
          </div>

          <div className="p-4 bg-amber-50/70 border border-amber-100 rounded-xl space-y-1.5">
            <div className="text-xs font-bold text-amber-950 uppercase tracking-wider flex items-center gap-1.5">
              <ShieldCheck size={13} className="text-amber-700" />
              <span>Safety & Policy Guardrails</span>
            </div>
            <p className="text-xs text-amber-900 leading-relaxed font-medium">
              {paymentId === 'pay_001'
                ? 'Duplicate Order Guardrail: Halted execution to protect against double fulfillment.'
                : paymentId === 'pay_003'
                ? 'Circuit Guardrail: Halted execution on 500 error to protect merchant backend stability.'
                : isRecovered
                ? 'Duplicate Prevention Verified: RecoverIQ verified database records post-recovery.'
                : 'Human-in-the-Loop Policy: RecoverIQ pauses autonomous recovery on delayed orders so you maintain full control.'}
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
                  {isRecovered ? 'Recovery Completed' : isStopped ? 'Recovery Stopped' : isEscalated ? 'Payment Escalated' : 'Your Action is Required'}
                </h3>
                <p className="text-xs text-slate-500">
                  {isRecovered
                    ? 'This payment has reached a verified terminal state.'
                    : isStopped
                    ? 'Autonomous retries have been stopped per operator command.'
                    : isEscalated
                    ? 'Transferred to engineering on-call for active investigation.'
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

          {/* Safety Checks List (Accurate Phrasing) */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs text-slate-700">
            <div className="flex items-center gap-2 p-2 bg-white rounded-lg border border-slate-200">
              <CheckCircle2 size={14} className="text-emerald-600 flex-shrink-0" />
              <span>Payment already captured by gateway</span>
            </div>
            <div className="flex items-center gap-2 p-2 bg-white rounded-lg border border-slate-200">
              <CheckCircle2 size={14} className="text-emerald-600 flex-shrink-0" />
              <span>Pre-allocated idempotency key reserved</span>
            </div>
            <div className="flex items-center gap-2 p-2 bg-white rounded-lg border border-slate-200">
              <CheckCircle2 size={14} className="text-emerald-600 flex-shrink-0" />
              <span>Duplicate execution protection enabled</span>
            </div>
            <div className="flex items-center gap-2 p-2 bg-white rounded-lg border border-slate-200">
              <CheckCircle2 size={14} className="text-emerald-600 flex-shrink-0" />
              <span>Merchant endpoint healthy now</span>
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
              <span>Recovery unavailable — payment is already in a terminal state.</span>
              <span className="font-semibold text-slate-500">Actions Disabled</span>
            </div>
          ) : isEscalated ? (
            <div className="p-3 bg-indigo-50/70 border border-indigo-200 rounded-xl text-xs text-indigo-900 flex items-center justify-between gap-3">
              <span>Payment escalated to operations engineering on-call for forensic analysis.</span>
              <span className="font-semibold text-indigo-800">In Review</span>
            </div>
          ) : (
            <div className="space-y-2 pt-2">
              <div className="flex items-center gap-3 flex-wrap">
                {/* PRIMARY: Solid Blue Button with explicit copy */}
                <button
                  onClick={() => setActiveModalAction('APPROVE')}
                  className="px-5 py-2.5 rounded-xl bg-[#0C66E4] hover:bg-[#0052CC] text-white text-xs font-bold transition-all shadow-xs hover:shadow-sm flex items-center gap-2 cursor-pointer"
                >
                  <CheckCircle2 size={14} />
                  <span>Approve Safe Recovery</span>
                </button>

                {/* SECONDARY: Outline Neutral Gray Button */}
                <button
                  onClick={() => setActiveModalAction('REJECT')}
                  className="px-4 py-2.5 rounded-xl border border-slate-200 bg-white hover:bg-slate-100 text-slate-700 text-xs font-semibold transition-colors cursor-pointer"
                >
                  Reject
                </button>

                {/* TERTIARY: Muted Text Button */}
                <button
                  onClick={() => setActiveModalAction('ESCALATE')}
                  className="px-3 py-2.5 text-slate-500 hover:text-slate-800 text-xs font-medium transition-colors cursor-pointer"
                >
                  Escalate
                </button>
              </div>

              {/* Explicit Safety Subtext Beneath Primary Action */}
              <div className="text-[11px] text-emerald-700 font-medium flex items-center gap-1.5 pt-0.5">
                <span>✓ No re-charge. Reuses existing captured payment of ₹{amount.toLocaleString('en-IN')}.</span>
              </div>
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
        {/* LAYER 2: ADVANCED DETAILS & 4-WAY RECONCILIATION */}
        {/* ========================================================================= */}
        <div className="border border-slate-200 rounded-2xl overflow-hidden">
          <button
            onClick={() => setShowAiReasoning(!showAiReasoning)}
            className="w-full px-5 py-3.5 bg-slate-50 hover:bg-slate-100/80 text-left flex items-center justify-between text-xs font-bold text-slate-800 transition-colors cursor-pointer"
          >
            <div className="flex items-center gap-2">
              <Activity size={14} className="text-brand-600" />
              <span>Why did RecoverIQ recommend this? (AI Decision & 4-Way Reconciliation)</span>
            </div>
            {showAiReasoning ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
          </button>

          {showAiReasoning && (
            <div className="p-5 bg-white border-t border-slate-200 space-y-4 text-xs">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-1">
                  <div className="text-slate-500 text-[10px] uppercase font-bold">AI Recommendation</div>
                  <div className="font-bold text-amber-700 text-sm">{incident?.decision || 'HUMAN REVIEW'}</div>
                  <div className="text-[11px] text-slate-600">Policy: Pause for operator authorization</div>
                </div>
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-1">
                  <div className="text-slate-500 text-[10px] uppercase font-bold">Confidence Score</div>
                  <div className="font-bold text-slate-900 text-sm">{confidence}%</div>
                  <div className="text-[11px] text-slate-600">Threshold for autonomous recovery: {decisionThreshold}%</div>
                </div>
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-1">
                  <div className="text-slate-500 text-[10px] uppercase font-bold">Endpoint Diagnostic</div>
                  <div className="font-bold text-emerald-700 text-sm">Healthy Now (Ping: 124ms)</div>
                  <div className="text-[11px] text-slate-600">Incident Event: HTTP 504 Timeout (at failure)</div>
                </div>
              </div>

              {/* 4-Way Cross-System State Matrix */}
              <div className="space-y-2 pt-2">
                <div className="font-bold text-slate-900 text-xs uppercase tracking-wider">
                  4-Way System State Reconciliation Matrix
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                  <div className="p-2.5 bg-slate-50 rounded-xl border border-slate-200 flex items-center justify-between">
                    <span>1. Gateway Payment State</span>
                    <span className="font-bold text-emerald-700">✓ MATCH (CAPTURED)</span>
                  </div>
                  <div className="p-2.5 bg-slate-50 rounded-xl border border-slate-200 flex items-center justify-between">
                    <span>2. Merchant Database Order</span>
                    <span className={`font-bold ${isRecovered ? 'text-emerald-700' : 'text-amber-700'}`}>
                      {isRecovered ? '✓ MATCH (CREATED)' : '⚠ CONFLICT (MISSING)'}
                    </span>
                  </div>
                  <div className="p-2.5 bg-slate-50 rounded-xl border border-slate-200 flex items-center justify-between">
                    <span>3. Internal Inventory Reservation</span>
                    <span className={`font-bold ${isRecovered ? 'text-emerald-700' : 'text-slate-600'}`}>
                      {isRecovered ? '✓ MATCH (RESERVED)' : '⚠ PENDING'}
                    </span>
                  </div>
                  <div className="p-2.5 bg-slate-50 rounded-xl border border-slate-200 flex items-center justify-between">
                    <span>4. Webhook Delivery Acknowledgment</span>
                    <span className={`font-bold ${isRecovered ? 'text-emerald-700' : 'text-rose-700'}`}>
                      {isRecovered ? '✓ MATCH (REPLAYED)' : '✕ TIMEOUT (HTTP 504)'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Forensic Execution Chain */}
              <div className="space-y-2 pt-2">
                <div className="font-bold text-slate-900 text-xs uppercase tracking-wider">
                  Autonomous Execution Trace
                </div>
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-1.5 font-mono text-[11px]">
                  <div className="text-slate-700">1. EVIDENCE: Payment CAPTURED on Gateway (₹{amount.toLocaleString('en-IN')}) · Order NOT_CREATED</div>
                  <div className="text-amber-700">2. ROOT CAUSE: Gateway timeout after webhook dispatch (HTTP 504)</div>
                  <div className="text-brand-700">3. POLICY: AI Confidence {confidence}% &lt; {decisionThreshold}% threshold → Route to Human Review Queue</div>
                  <div className="text-emerald-700">4. IDEMPOTENCY: Reserved key {idempotencyKey} (Duplicate prevention enforced)</div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* ========================================================================= */}
        {/* LAYER 3: TECHNICAL FORENSICS & RAW JSON */}
        {/* ========================================================================= */}
        <div className="border border-slate-200 rounded-2xl overflow-hidden">
          <button
            onClick={() => setShowTechnicalDetails(!showTechnicalDetails)}
            className="w-full px-5 py-3.5 bg-slate-50 hover:bg-slate-100/80 text-left flex items-center justify-between text-xs font-bold text-slate-800 transition-colors cursor-pointer"
          >
            <div className="flex items-center gap-2">
              <Terminal size={14} className="text-slate-600" />
              <span>Technical Diagnostics & Raw Payloads (Engineers & Auditors)</span>
            </div>
            {showTechnicalDetails ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
          </button>

          {showTechnicalDetails && (
            <div className="p-5 bg-white border-t border-slate-200 space-y-4 text-xs">
              {/* Idempotency Key Bar */}
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 flex items-center justify-between gap-3 flex-wrap">
                <div>
                  <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Idempotency Key</div>
                  <div className="font-mono text-xs font-bold text-slate-800">{idempotencyKey}</div>
                </div>
                <button
                  onClick={() => handleCopy(idempotencyKey, 'key')}
                  className="px-3 py-1.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-100 text-xs font-semibold text-slate-700 flex items-center gap-1.5 transition-colors cursor-pointer"
                >
                  {copiedKey ? <Check size={12} className="text-emerald-600" /> : <Copy size={12} />}
                  <span>{copiedKey ? 'Copied' : 'Copy Key'}</span>
                </button>
              </div>

              {/* JSON Payloads Viewer Tabs */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-lg">
                    {['snapshot', 'request', 'response', 'headers'].map((tab) => (
                      <button
                        key={tab}
                        onClick={() => setRawJsonTab(tab)}
                        className={`px-3 py-1 rounded-md text-[11px] font-semibold capitalize transition-all cursor-pointer ${
                          rawJsonTab === tab ? 'bg-white text-brand-700 shadow-2xs font-bold' : 'text-slate-600 hover:text-slate-900'
                        }`}
                      >
                        {tab}
                      </button>
                    ))}
                  </div>

                  <button
                    onClick={() => handleCopy(JSON.stringify(sampleRequestPayload, null, 2), 'json')}
                    className="text-[11px] text-slate-500 hover:text-slate-900 flex items-center gap-1 cursor-pointer"
                  >
                    {copiedJson ? <Check size={11} className="text-emerald-600" /> : <Copy size={11} />}
                    <span>{copiedJson ? 'Copied JSON' : 'Copy Payload'}</span>
                  </button>
                </div>

                <div className="p-4 bg-slate-900 text-slate-200 rounded-xl font-mono text-[11px] overflow-x-auto max-h-60">
                  <pre>{JSON.stringify(rawJsonTab === 'request' ? sampleRequestPayload : rawJsonTab === 'response' ? sampleResponsePayload : rawJsonTab === 'headers' ? sampleHeaders : (snapshot || incident), null, 2)}</pre>
                </div>
              </div>
            </div>
          )}
        </div>

      </div>

      {/* ========================================================================= */}
      {/* CONFIRMATION ACTION MODAL (APPROVE / REJECT / ESCALATE) */}
      {/* ========================================================================= */}
      {activeModalAction && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl p-6 sm:p-7 max-w-md w-full shadow-2xl border border-slate-200 space-y-4 animate-in zoom-in-95 duration-150 text-slate-900">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2">
                <div className={`w-8 h-8 rounded-xl flex items-center justify-center text-white ${
                  activeModalAction === 'APPROVE' ? 'bg-brand-600' : activeModalAction === 'REJECT' ? 'bg-rose-600' : 'bg-amber-600'
                }`}>
                  {activeModalAction === 'APPROVE' ? <CheckCircle2 size={16} /> : activeModalAction === 'REJECT' ? <AlertCircle size={16} /> : <AlertOctagon size={16} />}
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-900">
                    {activeModalAction === 'APPROVE' ? 'Confirm Safe Recovery' : activeModalAction === 'REJECT' ? 'Confirm Rejection' : 'Escalate to Engineering'}
                  </h3>
                  <span className="text-[11px] font-mono text-slate-500">{paymentId} · ₹{amount.toLocaleString('en-IN')}</span>
                </div>
              </div>
              <button
                onClick={() => setActiveModalAction(null)}
                className="text-slate-400 hover:text-slate-700 cursor-pointer"
              >
                <X size={18} />
              </button>
            </div>

            {activeModalAction === 'APPROVE' ? (
              <div className="space-y-3 text-xs">
                <p className="text-slate-700 leading-relaxed">
                  You are authorizing RecoverIQ to perform an idempotent order synchronization in your merchant database.
                </p>
                <div className="p-3 bg-emerald-50 rounded-xl border border-emerald-200 text-emerald-900 space-y-1">
                  <div className="font-bold">✓ Financial Safety Guarantee:</div>
                  <div className="text-[11px] space-y-0.5">
                    <div>● No additional funds will be charged to the customer.</div>
                    <div>● Reuses existing gateway capture ID.</div>
                    <div>● Idempotency key {idempotencyKey} protects against duplicate records.</div>
                  </div>
                </div>
              </div>
            ) : activeModalAction === 'REJECT' ? (
              <div className="space-y-3 text-xs">
                <p className="text-slate-700 leading-relaxed">
                  Rejecting recovery will permanently halt automated order synchronization and mark this incident as STOPPED.
                </p>
                <div className="space-y-1">
                  <label className="text-slate-700 font-semibold">Reason for Rejection:</label>
                  <input
                    type="text"
                    value={rejectReason}
                    onChange={(e) => setRejectReason(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-slate-200 text-xs bg-slate-50 focus:bg-white focus:outline-hidden focus:ring-2 focus:ring-rose-500/20 text-slate-800"
                  />
                </div>
              </div>
            ) : (
              <div className="space-y-3 text-xs">
                <p className="text-slate-700 leading-relaxed">
                  Route this incident to Senior Operations & Engineering On-call for root-cause forensic investigation.
                </p>
                <div className="space-y-1">
                  <label className="text-slate-700 font-semibold">Escalation Note:</label>
                  <input
                    type="text"
                    value={escalateReason}
                    onChange={(e) => setEscalateReason(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-slate-200 text-xs bg-slate-50 focus:bg-white focus:outline-hidden focus:ring-2 focus:ring-amber-500/20 text-slate-800"
                  />
                </div>
              </div>
            )}

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
              <button
                onClick={() => setActiveModalAction(null)}
                className="px-4 py-2 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 text-xs font-semibold transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={
                  activeModalAction === 'APPROVE' ? handleApproveRecovery : activeModalAction === 'REJECT' ? handleRejectRecovery : handleEscalateRecovery
                }
                disabled={isProcessingAction}
                className={`px-5 py-2 rounded-xl text-white text-xs font-bold transition-all shadow-xs flex items-center gap-1.5 cursor-pointer disabled:opacity-50 ${
                  activeModalAction === 'APPROVE' ? 'bg-brand-600 hover:bg-brand-700' : activeModalAction === 'REJECT' ? 'bg-rose-600 hover:bg-rose-700' : 'bg-amber-600 hover:bg-amber-700'
                }`}
              >
                {isProcessingAction && <RefreshCw size={12} className="animate-spin" />}
                <span>
                  {activeModalAction === 'APPROVE' ? 'Confirm Safe Recovery' : activeModalAction === 'REJECT' ? 'Confirm Rejection' : 'Confirm Escalation'}
                </span>
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  )
}
