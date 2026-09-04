import { useState } from 'react'
import {
  X, HelpCircle, Shield, CheckCircle2, AlertTriangle, AlertCircle, ShieldAlert,
  ArrowRight, Sparkles, BookOpen, Layers, Database, Key, Activity, FileText,
  Clock, Lock, Check, Zap, Eye, Terminal, FileSpreadsheet, FileCode, Search
} from 'lucide-react'

export default function HelpCenterModal({ isOpen, onClose, demoIncidents = [] }) {
  const [activeTab, setActiveTab] = useState('GUIDE') // 'GUIDE' | 'WORKFLOW' | 'AI_DECISION' | 'FEATURES' | 'DATASET' | 'GLOSSARY'
  const [copiedSection, setCopiedSection] = useState(null)

  if (!isOpen) return null

  // Fallback demo sample records if props empty
  const defaultDemoRecords = [
    { id: 'pay_001', amount: 8400, status: 'STOPPED', problem: 'Server timeout after webhook delivery', decision: 'STOP', desc: 'Halted to prevent duplicate order' },
    { id: 'pay_002', amount: 2500, status: 'AWAITING_REVIEW', problem: 'Customer card expired / network timeout', decision: 'HUMAN REVIEW', desc: 'Requires operator confirmation' },
    { id: 'pay_003', amount: 12000, status: 'STOPPED', problem: 'Merchant server error (500) during processing', decision: 'STOP', desc: 'Recovery blocked by safety policy' },
    { id: 'pay_004', amount: 5600, status: 'RECOVERED', problem: 'Merchant server timeout after webhook delivery', decision: 'AUTO RECOVERY', desc: 'Automatically recovered & synced' },
    { id: 'pay_005', amount: 3100, status: 'NEEDS_REVIEW', problem: 'Gateway captured, merchant order confirmation timed out', decision: 'HUMAN REVIEW', desc: 'Awaiting merchant approval' }
  ]

  const displayRecords = demoIncidents && demoIncidents.length >= 5
    ? demoIncidents.slice(0, 5).map(i => ({
        id: i.id,
        amount: i.amount,
        status: i.recoveryStatus === 'SUCCESS' || i.status === 'RECOVERED' ? 'RECOVERED' : i.status === 'STOPPED' ? 'STOPPED' : 'NEEDS_REVIEW',
        problem: i.rootCause || 'Webhook timeout',
        decision: i.decision || (i.id === 'pay_004' ? 'AUTO RECOVERY' : i.id === 'pay_003' || i.id === 'pay_001' ? 'STOP' : 'HUMAN REVIEW'),
        desc: i.recommendation || 'Evaluated per policy'
      }))
    : defaultDemoRecords

  const navTabs = [
    { id: 'GUIDE', label: '1. Overview & Value', icon: BookOpen },
    { id: 'WORKFLOW', label: '2. Step-by-Step Guide', icon: Layers },
    { id: 'AI_DECISION', label: '3. AI Recovery Decisions', icon: BrainIcon },
    { id: 'FEATURES', label: '4. Features & File Analysis', icon: FileText },
    { id: 'DATASET', label: '5. Demo Data & Demo Flow', icon: Terminal },
    { id: 'GLOSSARY', label: '6. Fintech Glossary', icon: HelpCircle }
  ]

  function BrainIcon(props) {
    return <Zap {...props} />
  }

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-3 sm:p-5 animate-in fade-in duration-150">
      <div className="bg-white border border-slate-200 rounded-3xl shadow-2xl max-w-4xl w-full max-h-[90vh] flex flex-col overflow-hidden">
        
        {/* TOP BAR: Product Header & Close */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/80">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-brand-600 flex items-center justify-center text-white shadow-xs">
              <Shield size={18} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-slate-900 leading-none">
                  Recover<span className="text-brand-600">IQ</span>
                </h2>
                <span className="text-[10px] font-bold text-brand-700 bg-brand-50 px-2 py-0.5 rounded border border-brand-200">
                  PRODUCT GUIDE & HELP
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-0.5 font-medium">
                AI-powered Post-Payment Recovery & Operator Orchestration
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="w-8 h-8 rounded-xl hover:bg-slate-200 text-slate-400 hover:text-slate-700 flex items-center justify-center transition-colors cursor-pointer"
          >
            <X size={18} />
          </button>
        </div>

        {/* SUB-NAV TABS */}
        <div className="px-6 py-2 border-b border-slate-100 bg-white flex items-center gap-1.5 overflow-x-auto">
          {navTabs.map(t => {
            const Icon = t.icon
            const isActive = activeTab === t.id
            return (
              <button
                key={t.id}
                onClick={() => setActiveTab(t.id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold transition-all whitespace-nowrap cursor-pointer ${
                  isActive
                    ? 'bg-brand-50 text-brand-700 border border-brand-200 shadow-2xs'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                }`}
              >
                <Icon size={13} />
                <span>{t.label}</span>
              </button>
            )
          })}
        </div>

        {/* MAIN BODY SCROLLABLE AREA */}
        <div className="p-6 overflow-y-auto space-y-6 text-xs flex-1">

          {/* TAB 1: OVERVIEW & 4 CORE VALUES */}
          {activeTab === 'GUIDE' && (
            <div className="space-y-6">
              {/* Value Intro Banner */}
              <div className="p-5 bg-gradient-to-r from-brand-50 via-blue-50/40 to-slate-50 border border-brand-100 rounded-2xl space-y-2">
                <span className="text-[10px] font-bold uppercase tracking-wider text-brand-700">What RecoverIQ Does</span>
                <h3 className="text-sm font-bold text-slate-900">
                  Autonomous payment recovery that protects revenue without double-charging customers.
                </h3>
                <p className="text-xs text-slate-600 leading-relaxed">
                  RecoverIQ helps merchants detect failed or uncertain payment workflows, understand why they happened, decide the safest recovery action, and verify that the payment state is correct — without duplicate recovery attempts.
                </p>
              </div>

              {/* 4 Core Value Pillars */}
              <div className="space-y-2">
                <div className="text-xs font-bold text-slate-800 uppercase tracking-wider">The 4-Step Recovery Loop</div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="p-4 bg-slate-50 border border-slate-200/80 rounded-2xl space-y-1.5 shadow-2xs">
                    <div className="flex items-center gap-2">
                      <span className="w-6 h-6 rounded-lg bg-blue-100 text-blue-800 font-bold flex items-center justify-center text-xs">1</span>
                      <h4 className="font-bold text-slate-900 text-xs">Detect</h4>
                    </div>
                    <p className="text-slate-600 text-[11px] leading-relaxed">
                      Identify payment failures, uncertain states, webhook delivery dropouts, and recoverable candidates in real time.
                    </p>
                  </div>

                  <div className="p-4 bg-slate-50 border border-slate-200/80 rounded-2xl space-y-1.5 shadow-2xs">
                    <div className="flex items-center gap-2">
                      <span className="w-6 h-6 rounded-lg bg-indigo-100 text-indigo-800 font-bold flex items-center justify-center text-xs">2</span>
                      <h4 className="font-bold text-slate-900 text-xs">Understand</h4>
                    </div>
                    <p className="text-slate-600 text-[11px] leading-relaxed">
                      Analyze gateway responses, retry counts, endpoint health, and run 4-way reconciliation between Gateway, DB, and Webhooks.
                    </p>
                  </div>

                  <div className="p-4 bg-slate-50 border border-slate-200/80 rounded-2xl space-y-1.5 shadow-2xs">
                    <div className="flex items-center gap-2">
                      <span className="w-6 h-6 rounded-lg bg-amber-100 text-amber-800 font-bold flex items-center justify-center text-xs">3</span>
                      <h4 className="font-bold text-slate-900 text-xs">Decide</h4>
                    </div>
                    <p className="text-slate-600 text-[11px] leading-relaxed">
                      Use confidence scores and policy rules to determine whether to Auto Recover, enqueue for Human Review, or Stop recovery.
                    </p>
                  </div>

                  <div className="p-4 bg-slate-50 border border-slate-200/80 rounded-2xl space-y-1.5 shadow-2xs">
                    <div className="flex items-center gap-2">
                      <span className="w-6 h-6 rounded-lg bg-emerald-100 text-emerald-800 font-bold flex items-center justify-center text-xs">4</span>
                      <h4 className="font-bold text-slate-900 text-xs">Verify</h4>
                    </div>
                    <p className="text-slate-600 text-[11px] leading-relaxed">
                      Confirm the resulting payment state and database order creation, recording every transition in a tamper-evident audit trail.
                    </p>
                  </div>
                </div>
              </div>

              {/* Navigation Quick Summary */}
              <div className="p-4 bg-slate-50 border border-slate-200 rounded-2xl space-y-2">
                <span className="text-xs font-bold text-slate-800 uppercase tracking-wider">Dashboard Navigation Guide</span>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-[11px]">
                  <div className="p-2 bg-white rounded-xl border border-slate-200">
                    <strong className="text-brand-700">Overview:</strong> What needs attention right now?
                  </div>
                  <div className="p-2 bg-white rounded-xl border border-slate-200">
                    <strong className="text-brand-700">Payments:</strong> Individual cases & 3-layer details.
                  </div>
                  <div className="p-2 bg-white rounded-xl border border-slate-200">
                    <strong className="text-brand-700">File Analysis:</strong> Batch files, quarantine & recovery plans.
                  </div>
                  <div className="p-2 bg-white rounded-xl border border-slate-200">
                    <strong className="text-brand-700">Activity:</strong> Real-time agent event stream.
                  </div>
                  <div className="p-2 bg-white rounded-xl border border-slate-200">
                    <strong className="text-brand-700">Audit:</strong> Immutable compliance ledger.
                  </div>
                  <div className="p-2 bg-white rounded-xl border border-slate-200">
                    <strong className="text-brand-700">Demo Sandbox:</strong> Reproduce failure scenarios safely.
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: STEP-BY-STEP USER GUIDE */}
          {activeTab === 'WORKFLOW' && (
            <div className="space-y-4">
              <div className="space-y-1">
                <h3 className="text-sm font-bold text-slate-900">How to Use RecoverIQ — 6-Step Visual Walkthrough</h3>
                <p className="text-slate-500 text-xs">Follow this operational workflow to manage your payment health effortlessly.</p>
              </div>

              <div className="space-y-3">
                {/* Step 1 */}
                <div className="p-4 bg-slate-50 border border-slate-200 rounded-2xl space-y-1.5">
                  <div className="flex items-center gap-2 text-xs font-bold text-slate-900">
                    <span className="w-5 h-5 rounded-full bg-brand-600 text-white flex items-center justify-center text-[10px]">1</span>
                    <span>Start at the Overview Command Center</span>
                  </div>
                  <p className="text-slate-600 text-[11px] leading-relaxed pl-7">
                    The Overview shows real-time metrics: <strong>Money at Risk</strong> (unresolved captured payments), <strong>Money Recovered</strong> (safely recovered revenue), <strong>Needs Attention</strong> (actionable items), and <strong>Recovery Rate</strong>. Start here to quickly see if any payment requires your authorization.
                  </p>
                </div>

                {/* Step 2 */}
                <div className="p-4 bg-slate-50 border border-slate-200 rounded-2xl space-y-1.5">
                  <div className="flex items-center gap-2 text-xs font-bold text-slate-900">
                    <span className="w-5 h-5 rounded-full bg-brand-600 text-white flex items-center justify-center text-[10px]">2</span>
                    <span>Review Payments Workspace</span>
                  </div>
                  <p className="text-slate-600 text-[11px] leading-relaxed pl-7">
                    Open the <strong>Payments</strong> workspace to see all transactions. Filter by <em>Needs Attention</em>, <em>Recovered</em>, or <em>Stopped</em>, search by payment/order ID, and click any payment to inspect its full operational history.
                  </p>
                </div>

                {/* Step 3 */}
                <div className="p-4 bg-slate-50 border border-slate-200 rounded-2xl space-y-1.5">
                  <div className="flex items-center gap-2 text-xs font-bold text-slate-900">
                    <span className="w-5 h-5 rounded-full bg-brand-600 text-white flex items-center justify-center text-[10px]">3</span>
                    <span>Inspect 3-Layer Payment Details</span>
                  </div>
                  <p className="text-slate-600 text-[11px] leading-relaxed pl-7">
                    <strong>Layer 1 (Merchant View)</strong> answers <em>What Happened?</em> and <em>What is RecoverIQ Doing?</em> in plain English. <strong>Layer 2 (AI Intelligence)</strong> displays 4-way reconciliation signals. <strong>Layer 3 (Observability)</strong> displays raw masked JSON payloads, traces, and HMAC signatures. RecoverIQ evaluates evidence per policy rather than blindly retrying.
                  </p>
                </div>

                {/* Step 4 */}
                <div className="p-4 bg-slate-50 border border-slate-200 rounded-2xl space-y-1.5">
                  <div className="flex items-center gap-2 text-xs font-bold text-slate-900">
                    <span className="w-5 h-5 rounded-full bg-brand-600 text-white flex items-center justify-center text-[10px]">4</span>
                    <span>Authorize or Reject in the Human Action Center</span>
                  </div>
                  <p className="text-slate-600 text-[11px] leading-relaxed pl-7">
                    When confidence is below 85% or an action is sensitive, RecoverIQ routes to <strong>Human Review</strong>. Click <strong>[Approve Recovery]</strong> to execute idempotent order sync, <strong>[Reject]</strong> to permanently halt retries, or <strong>[Escalate]</strong> to page senior engineering on-call. Terminal payments are locked against duplicate actions.
                  </p>
                </div>

                {/* Step 5 */}
                <div className="p-4 bg-slate-50 border border-slate-200 rounded-2xl space-y-1.5">
                  <div className="flex items-center gap-2 text-xs font-bold text-slate-900">
                    <span className="w-5 h-5 rounded-full bg-brand-600 text-white flex items-center justify-center text-[10px]">5</span>
                    <span>Verify Post-Recovery State</span>
                  </div>
                  <p className="text-slate-600 text-[11px] leading-relaxed pl-7">
                    After executing a recovery, RecoverIQ verifies the database order creation rather than assuming success. The state advances to <strong>RECOVERED</strong> and metrics recalculate dynamically.
                  </p>
                </div>

                {/* Step 6 */}
                <div className="p-4 bg-slate-50 border border-slate-200 rounded-2xl space-y-1.5">
                  <div className="flex items-center gap-2 text-xs font-bold text-slate-900">
                    <span className="w-5 h-5 rounded-full bg-brand-600 text-white flex items-center justify-center text-[10px]">6</span>
                    <span>Audit Traceability & Activity Stream</span>
                  </div>
                  <p className="text-slate-600 text-[11px] leading-relaxed pl-7">
                    The <strong>Activity</strong> page records background agent events with an optional Technical Details view. The <strong>Audit</strong> ledger provides an immutable compliance record with copyable idempotency keys.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: AI DECISION EXPLAINABILITY */}
          {activeTab === 'AI_DECISION' && (
            <div className="space-y-5">
              <div className="space-y-1">
                <h3 className="text-sm font-bold text-slate-900">How the AI Recovery Decision Works</h3>
                <p className="text-slate-500 text-xs">
                  AI recommendations are governed by deterministic recovery policies, reconciliation signals, and safety guardrails.
                </p>
              </div>

              {/* Signals Evaluated */}
              <div className="p-4 bg-slate-50 border border-slate-200 rounded-2xl space-y-2">
                <div className="font-bold text-slate-800 text-xs">Signals Evaluated Before Decision:</div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px]">
                  <div className="p-2 bg-white rounded-lg border border-slate-200 font-medium text-slate-700">
                    ● Payment Gateway Status
                  </div>
                  <div className="p-2 bg-white rounded-lg border border-slate-200 font-medium text-slate-700">
                    ● Merchant DB Order Status
                  </div>
                  <div className="p-2 bg-white rounded-lg border border-slate-200 font-medium text-slate-700">
                    ● Retry Counter (&lt; 2)
                  </div>
                  <div className="p-2 bg-white rounded-lg border border-slate-200 font-medium text-slate-700">
                    ● Endpoint Health &amp; Breaker
                  </div>
                  <div className="p-2 bg-white rounded-lg border border-slate-200 font-medium text-slate-700">
                    ● Webhook HMAC Signature
                  </div>
                  <div className="p-2 bg-white rounded-lg border border-slate-200 font-medium text-slate-700">
                    ● Duplicate Key Reservation
                  </div>
                  <div className="p-2 bg-white rounded-lg border border-slate-200 font-medium text-slate-700">
                    ● HTTP Status Code (504 vs 4xx)
                  </div>
                  <div className="p-2 bg-white rounded-lg border border-slate-200 font-medium text-slate-700">
                    ● 4-Way Reconciliation
                  </div>
                </div>
              </div>

              {/* 3 Possible Outcomes */}
              <div className="space-y-2">
                <div className="font-bold text-slate-800 text-xs">Three Authoritative Policy Outcomes:</div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div className="p-4 bg-emerald-50/70 border border-emerald-200 rounded-2xl space-y-1.5">
                    <div className="flex items-center gap-1.5 font-bold text-emerald-900 text-xs">
                      <CheckCircle2 size={14} className="text-emerald-600" />
                      <span>AUTO RECOVERY</span>
                    </div>
                    <p className="text-emerald-800 text-[11px] leading-relaxed">
                      High confidence (&ge;85%), zero duplicate order in DB, retries within limit. Safe idempotent order sync proceeds automatically.
                    </p>
                  </div>

                  <div className="p-4 bg-amber-50/70 border border-amber-200 rounded-2xl space-y-1.5">
                    <div className="flex items-center gap-1.5 font-bold text-amber-900 text-xs">
                      <AlertTriangle size={14} className="text-amber-700" />
                      <span>HUMAN REVIEW</span>
                    </div>
                    <p className="text-amber-800 text-[11px] leading-relaxed">
                      Sub-85% confidence, ambiguous state, or delayed order. Pauses autonomous recovery so the merchant can authorize.
                    </p>
                  </div>

                  <div className="p-4 bg-slate-100 border border-slate-300 rounded-2xl space-y-1.5">
                    <div className="flex items-center gap-1.5 font-bold text-slate-900 text-xs">
                      <ShieldAlert size={14} className="text-slate-600" />
                      <span>STOP</span>
                    </div>
                    <p className="text-slate-700 text-[11px] leading-relaxed">
                      Order already exists in DB, invalid signature, or card expired. Halts recovery immediately to prevent double-charging.
                    </p>
                  </div>
                </div>
              </div>

              {/* Safety Invariant Banner */}
              <div className="p-3.5 bg-blue-50 border border-blue-200 text-blue-900 rounded-2xl text-[11px] font-medium leading-relaxed">
                <strong>Deterministic Safety Guarantee:</strong> All AI recommendations are strictly constrained by Python safety invariants. If external AI services are unreachable, deterministic rule engines take over seamlessly.
              </div>
            </div>
          )}

          {/* TAB 4: MAJOR FEATURES & FILE ANALYSIS */}
          {activeTab === 'FEATURES' && (
            <div className="space-y-5">
              <div className="space-y-1">
                <h3 className="text-sm font-bold text-slate-900">What RecoverIQ Handles — Platform Capabilities</h3>
                <p className="text-slate-500 text-xs">Comprehensive fintech resiliency features built into every payment journey.</p>
              </div>

              {/* 12 Platform Features Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {[
                  { title: 'Payment State Machine', desc: 'Keeps payment states consistent and prevents invalid transitions.', icon: Layers },
                  { title: 'Webhook Security', desc: 'Validates HMAC-SHA256 signatures against replay and payload tampering.', icon: Lock },
                  { title: 'Idempotency', desc: 'Pre-allocates deterministic keys to enforce idempotent execution and prevent duplicate executions.', icon: Key },
                  { title: 'Intelligent Retry', desc: 'Controls retry behavior per policy instead of repeatedly retrying blindly.', icon: Clock },
                  { title: 'Circuit Breaker', desc: 'Pauses recovery when downstream merchant endpoints fail consecutive health checks.', icon: ShieldAlert },
                  { title: 'Reconciliation', desc: '4-way checks across Gateway, Merchant DB, Webhook, and internal state.', icon: Database },
                  { title: 'Human-in-the-Loop', desc: 'Empowers merchants to review and approve sensitive financial actions.', icon: CheckCircle2 },
                  { title: 'Explainability', desc: 'Plain-English breakdown of why a recommendation was made.', icon: Eye },
                  { title: 'Audit Trail', desc: 'Tamper-evident audit trail of every decision, actor, and verification.', icon: Shield },
                  { title: 'File Analysis', desc: 'Multi-format ingestion workspace with schema validation & anomaly triage.', icon: FileText },
                  { title: 'Selective Batch Recovery', desc: 'Selectively recover valid payments with pre-execution safety review.', icon: Zap },
                  { title: 'Observability', desc: 'Distributed trace spans, latencies, and 4-tab raw masked JSON payloads.', icon: Activity },
                ].map((feat, idx) => {
                  const Icon = feat.icon
                  return (
                    <div key={idx} className="p-3.5 bg-slate-50 border border-slate-200 rounded-xl space-y-1">
                      <div className="flex items-center gap-1.5 font-bold text-slate-900 text-xs">
                        <Icon size={13} className="text-brand-600" />
                        <span>{feat.title}</span>
                      </div>
                      <p className="text-slate-600 text-[11px] leading-relaxed">{feat.desc}</p>
                    </div>
                  )
                })}
              </div>

              {/* Dedicated File Analysis Section */}
              <div className="p-5 bg-white border border-slate-200 rounded-2xl space-y-3 shadow-xs">
                <div className="flex items-center gap-2">
                  <FileSpreadsheet size={16} className="text-brand-600" />
                  <h4 className="font-bold text-slate-900 text-xs uppercase tracking-wider">Analyze Payment Files</h4>
                </div>
                <p className="text-slate-600 text-xs leading-relaxed">
                  You can upload payment data and RecoverIQ will analyze the records before any recovery action is considered.
                </p>

                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 font-mono text-[11px] text-brand-800">
                  Upload → Validate → Analyze → Detect Issues → Quarantine Invalid Records → Build Recovery Plan → Select Eligible Payments → Execute Recovery → Verify Results
                </div>

                <div className="text-[11px] text-slate-600 space-y-1">
                  <div><strong>Supported Formats:</strong> CSV, Excel (XLSX, XLS), JSON, TXT, PDF, DOCX</div>
                  <div><strong>Features:</strong> Quarantine queue triage, inline [Fix &amp; Reprocess] modal, contextual NLP assistant, and live 6-stage sequential batch execution.</div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 5: 5 DEMO RECORDS & RECOMMENDED DEMO FLOW */}
          {activeTab === 'DATASET' && (
            <div className="space-y-5">
              
              {/* Sandbox Notice Banner */}
              <div className="p-4 bg-amber-50 border border-amber-200 rounded-2xl space-y-1">
                <div className="flex items-center gap-2 font-bold text-amber-950 text-xs">
                  <Terminal size={14} className="text-amber-700" />
                  <span>Demo &amp; Sandbox Environment</span>
                </div>
                <p className="text-amber-900 text-[11px] leading-relaxed">
                  Recovery actions in this demonstration use a sandbox/mock recovery environment. No real customer payments, refunds, or financial transactions are performed. The sandbox allows the recovery workflow, state transitions, idempotency, verification, reconciliation, and audit behavior to be demonstrated safely.
                </p>
              </div>

              {/* 5 Demo Records Table */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-slate-900 text-xs uppercase tracking-wider">Demo Dataset (5 Sample Records)</span>
                  <span className="text-[10px] text-slate-500 font-medium">5 sample payment records are included for demonstration</span>
                </div>

                <div className="border border-slate-200 rounded-2xl overflow-hidden shadow-2xs">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-bold uppercase text-[10px]">
                      <tr>
                        <th className="px-4 py-2.5">Payment ID</th>
                        <th className="px-4 py-2.5">Amount</th>
                        <th className="px-4 py-2.5">Diagnosed Problem</th>
                        <th className="px-4 py-2.5">Current Status</th>
                        <th className="px-4 py-2.5">AI Policy Decision</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 bg-white font-mono text-[11px]">
                      {displayRecords.map(r => (
                        <tr key={r.id} className="hover:bg-slate-50">
                          <td className="px-4 py-2.5 font-bold text-brand-700">{r.id}</td>
                          <td className="px-4 py-2.5 font-bold text-slate-900">₹{r.amount.toLocaleString('en-IN')}</td>
                          <td className="px-4 py-2.5 font-sans text-slate-700 truncate max-w-xs">{r.problem}</td>
                          <td className="px-4 py-2.5">
                            <span className={`inline-flex px-2 py-0.5 rounded-full text-[10px] font-bold ${
                              r.status === 'RECOVERED' ? 'bg-emerald-50 text-emerald-800 border border-emerald-200' :
                              r.status === 'STOPPED' ? 'bg-slate-100 text-slate-700 border border-slate-200' :
                              'bg-amber-50 text-amber-800 border border-amber-200'
                            }`}>
                              {r.status}
                            </span>
                          </td>
                          <td className="px-4 py-2.5 font-sans font-semibold text-slate-800">{r.decision}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Recommended Demo Flow */}
              <div className="p-5 bg-slate-50 border border-slate-200 rounded-2xl space-y-3">
                <div className="font-bold text-slate-900 text-xs uppercase tracking-wider">Recommended Demo Flow for Evaluators &amp; Judges</div>
                
                <div className="space-y-1.5 text-[11px] text-slate-700">
                  <div className="font-bold text-slate-900">A. Single Payment Recovery Journey:</div>
                  <ol className="list-decimal list-inside space-y-1 pl-2 text-slate-600">
                    <li>Open <strong>Overview</strong> and see payments requiring attention (<code>pay_005</code>).</li>
                    <li>Click <strong>Review Payment</strong> on <code>pay_005</code> to open the Payments workspace.</li>
                    <li>Inspect <strong>Layer 1</strong> plain-English explanation, <strong>Layer 2</strong> 4-way reconciliation, and <strong>Layer 3</strong> masked JSON observability.</li>
                    <li>Click <strong>[Approve Recovery]</strong> in the Human Action Center.</li>
                    <li>Observe live state transition to <code>RECOVERED</code> and live Activity feed events.</li>
                    <li>Open <strong>Audit</strong> to inspect the audit trail entry and copy the idempotency key.</li>
                  </ol>
                </div>

                <div className="space-y-1.5 text-[11px] text-slate-700 pt-2 border-t border-slate-200">
                  <div className="font-bold text-slate-900">B. Multi-Format Batch Intelligence Flow:</div>
                  <ol className="list-decimal list-inside space-y-1 pl-2 text-slate-600">
                    <li>Open <strong>File Analysis</strong> and click <strong>[Load Sample 10-Payment File]</strong>.</li>
                    <li>Review Ingestion Quality score and 5 Quality Diagnostic cards.</li>
                    <li>Switch to <strong>Quarantine Queue</strong> → click <strong>[Fix &amp; Reprocess]</strong> to unblock the corrupted row.</li>
                    <li>Select payments → click <strong>[Review Recovery Plan]</strong> → review safety modal.</li>
                    <li>Click <strong>[Execute Safe Recovery]</strong> and observe the sequential 6-stage tracker.</li>
                  </ol>
                </div>
              </div>

            </div>
          )}

          {/* TAB 6: GLOSSARY */}
          {activeTab === 'GLOSSARY' && (
            <div className="space-y-4">
              <div className="space-y-1">
                <h3 className="text-sm font-bold text-slate-900">Merchant-Friendly Fintech Glossary</h3>
                <p className="text-slate-500 text-xs">Quick definitions for key payment recovery concepts.</p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {[
                  { term: 'Recovery', def: 'An attempt to move a failed or uncertain payment workflow toward the correct final state.' },
                  { term: 'Human Review', def: 'A case where an operator must approve the recommended action before financial execution.' },
                  { term: 'Idempotency', def: 'A safety mechanism that prevents the same operation from being executed more than once.' },
                  { term: 'Reconciliation', def: 'Checking whether payment records and expected states agree across all systems.' },
                  { term: 'Circuit Breaker', def: 'A protection mechanism that pauses recovery when a downstream service is unhealthy.' },
                  { term: 'Quarantine', def: 'A temporary holding area for records that need correction before processing.' },
                  { term: 'Recovery Plan', def: 'The set of payments that are eligible for recovery and the actions proposed for them.' },
                  { term: 'Terminal State', def: 'A final payment state where additional recovery actions are no longer allowed.' }
                ].map((g, idx) => (
                  <div key={idx} className="p-3.5 bg-slate-50 border border-slate-200 rounded-xl space-y-1">
                    <div className="font-bold text-brand-800 text-xs">{g.term}</div>
                    <p className="text-slate-600 text-[11px] leading-relaxed">{g.def}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

        </div>

        {/* BOTTOM FOOTER */}
        <div className="px-6 py-3.5 bg-slate-50 border-t border-slate-100 flex items-center justify-between text-xs">
          <div className="text-slate-500 font-medium text-[11px]">
            Need to reset demo state? Use the <strong>Reset</strong> button in the navigation bar.
          </div>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-xl bg-slate-900 text-white font-bold cursor-pointer hover:bg-slate-800 transition-colors"
          >
            Got it, return to Dashboard
          </button>
        </div>

      </div>
    </div>
  )
}
