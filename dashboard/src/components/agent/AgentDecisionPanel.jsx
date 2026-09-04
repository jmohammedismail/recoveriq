import { useState, useEffect } from 'react'
import { Brain, ShieldCheck, ChevronDown, ChevronUp, Cpu } from 'lucide-react'
import { investigateIncidentWithAI } from '../../services/api'

export default function AgentDecisionPanel({ incident }) {
  const [liveAIResult, setLiveAIResult] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isExpanded, setIsExpanded] = useState(false)

  useEffect(() => {
    if (!incident || !incident.id) return
    let isCurrent = true
    setIsLoading(true)

    async function loadAI() {
      try {
        const res = await investigateIncidentWithAI(incident.id)
        if (isCurrent && res) {
          setLiveAIResult(res)
        }
      } catch (err) {
        console.warn('AI investigation fetch warning:', err)
      } finally {
        if (isCurrent) setIsLoading(false)
      }
    }

    loadAI()
    return () => { isCurrent = false }
  }, [incident?.id])

  if (!incident) {
    return (
      <div className="p-5 text-center bg-white border border-slate-200 rounded-2xl">
        <Brain size={20} className="text-slate-300 mx-auto mb-1.5" />
        <p className="text-xs text-slate-500 font-medium">Select an incident to view AI decision & governance</p>
      </div>
    )
  }

  // Use real backend analysis fields
  const aiData = liveAIResult?.agent || incident.ai_analysis || {}
  const recommendation = aiData.recommendation || incident.decision || 'HUMAN REVIEW'
  const confidence = aiData.confidence !== undefined ? aiData.confidence : incident.confidence
  const rootCause = aiData.root_cause || incident.rootCause
  const riskLevel = aiData.risk_level || 'LOW'
  const reasoning = aiData.reasoning_summary || incident.decisionExplanation || incident.explanation
  const nextAction = aiData.recommended_next_action || 'IDEMPOTENT_ORDER_SYNC'

  const isAuto = recommendation === 'AUTO RECOVERY'
  const isReview = recommendation === 'HUMAN REVIEW'

  return (
    <div className="bg-white border border-slate-200 rounded-2xl shadow-xs p-4 sm:p-5 space-y-3.5">
      
      {/* Header */}
      <div className="flex items-center justify-between pb-2.5 border-b border-slate-100 flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <Brain size={16} className="text-brand-600" />
          <span className="text-xs font-bold text-slate-800 uppercase tracking-wider">AI Decision & Result</span>
          <span className="font-mono text-xs font-bold text-brand-700 bg-brand-50 px-2 py-0.5 rounded border border-brand-200">
            {incident.id}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {isLoading && <span className="text-[10px] text-slate-400 font-mono animate-pulse">Running AI Reasoner...</span>}
          <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold uppercase tracking-tight ${
            isAuto 
              ? 'bg-emerald-50 text-emerald-800 border border-emerald-200' 
              : isReview 
              ? 'bg-amber-50 text-amber-800 border border-amber-200' 
              : 'bg-rose-50 text-rose-800 border border-rose-200'
          }`}>
            AI: {recommendation}
          </span>
        </div>
      </div>

      {/* Primary KPI Grid (Confidence, Risk, Policy, Governed Decision) */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {/* 1. Confidence */}
        <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200">
          <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Confidence</div>
          <div className="text-base font-bold font-mono text-slate-900 mt-0.5">
            {confidence}%
          </div>
        </div>

        {/* 2. Risk */}
        <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200">
          <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Risk Level</div>
          <div className={`text-xs font-bold mt-1 ${
            riskLevel === 'LOW' ? 'text-emerald-700' : riskLevel === 'MEDIUM' ? 'text-amber-700' : 'text-rose-700'
          }`}>
            {riskLevel}
          </div>
        </div>

        {/* 3. Policy Recommendation */}
        <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200">
          <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Policy Gate</div>
          <div className="text-xs font-bold text-slate-800 mt-1 truncate">
            {recommendation}
          </div>
        </div>

        {/* 4. Governed Result */}
        <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200">
          <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Python Result</div>
          <div className="text-xs font-extrabold font-mono text-brand-700 mt-1">
            {incident.recoveryStatus}
          </div>
        </div>
      </div>

      {/* Diagnosed Root Cause */}
      <div className="p-2.5 rounded-xl bg-blue-50/60 border border-blue-100 text-xs text-slate-700 flex items-start gap-2">
        <Cpu size={14} className="text-brand-600 flex-shrink-0 mt-0.5" />
        <div>
          <span className="font-bold text-slate-900">Diagnosed Root Cause: </span>
          <span>{rootCause}</span>
        </div>
      </div>

      {/* Expand / Collapse Button */}
      <div>
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="w-full flex items-center justify-between px-3 py-1.5 rounded-xl bg-slate-50 hover:bg-slate-100 text-xs font-semibold text-slate-700 border border-slate-200 transition-colors"
        >
          <span>{isExpanded ? 'Hide Detailed Reasoning' : 'View Detailed Reasoning'}</span>
          {isExpanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
        </button>
      </div>

      {/* Expandable Reasoning & Governance */}
      {isExpanded && (
        <div className="space-y-2.5 pt-1">
          {/* AI Executive Reasoning */}
          <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 space-y-1">
            <div className="text-[11px] font-bold text-slate-800 uppercase tracking-wider">AI Executive Reasoning</div>
            <p className="text-xs text-slate-600 leading-relaxed pt-0.5">
              {reasoning}
            </p>
            <div className="text-[11px] font-mono text-brand-700 pt-1">
              Action Proposed: {nextAction}
            </div>
          </div>

          {/* Authoritative Python Guardrail Check */}
          <div className={`p-3 rounded-xl border ${
            incident.recoveryStatus === 'STOPPED'
              ? 'bg-amber-50/70 border-amber-200 text-amber-900'
              : incident.recoveryStatus === 'SUCCESS'
              ? 'bg-emerald-50/70 border-emerald-200 text-emerald-900'
              : 'bg-slate-50 border-slate-200 text-slate-800'
          }`}>
            <div className="flex items-start gap-2">
              <ShieldCheck size={15} className={
                incident.recoveryStatus === 'SUCCESS' ? 'text-emerald-600 flex-shrink-0 mt-0.5' : incident.recoveryStatus === 'STOPPED' ? 'text-amber-600 flex-shrink-0 mt-0.5' : 'text-slate-600 flex-shrink-0 mt-0.5'
              } />
              <div>
                <div className="text-xs font-bold">
                  {incident.recoveryStatus === 'STOPPED'
                    ? 'Python Guardrail Override: Duplicate Order Prevented'
                    : incident.recoveryStatus === 'SUCCESS'
                    ? 'Python Guardrails Approved & Idempotent Sync Executed'
                    : 'Python Policy Gate: Enqueued for Merchant Review'}
                </div>
                <div className="text-[11px] text-slate-600 mt-0.5">
                  {incident.merchantOrderExists
                    ? 'Order presence verified in merchant DB · Autonomous recovery halted.'
                    : incident.recoveryStatus === 'SUCCESS'
                    ? 'Idempotency key generated · Pre-recovery DB absent · Sync confirmed.'
                    : `Retry count (${incident.retryCount}/2) verified · Awaiting operator approval.`}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
