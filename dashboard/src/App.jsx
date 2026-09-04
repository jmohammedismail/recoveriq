import { useState, useEffect, useCallback, useRef } from 'react'
import { AuthProvider, useAuth } from './context/AuthContext'
import LoginPage from './components/auth/LoginPage'
import TopNav from './components/layout/TopNav'
import StatusBar from './components/layout/StatusBar'
import AgentStatusHero from './components/overview/AgentStatusHero'
import MetricsRail from './components/overview/MetricsRail'
import NeedsAttentionSection from './components/overview/NeedsAttentionSection'
import RevenueChart from './components/overview/RevenueChart'
import IncidentTable from './components/incidents/IncidentTable'
import IncidentDetailPanel from './components/incidents/IncidentDetailPanel'
import FileUploadModal from './components/upload/FileUploadModal'
import FileAnalysisWorkspace from './components/upload/FileAnalysisWorkspace'
import LiveActivityFeed from './components/activity/LiveActivityFeed'
import AuditTrail from './components/audit/AuditTrail'
import { fetchIncidents, fetchMetrics, fetchAuditLogs, triggerRunPythonAgent, fetchAgentStatus } from './services/api'
import { incidents as fallbackIncidents } from './data/incidents'
import { metrics as fallbackMetrics } from './data/metrics'
import { ShieldCheck, Zap, AlertTriangle, AlertOctagon, ShieldAlert, CheckCircle2 } from 'lucide-react'

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

  const recoveredAmount = metricsData?.revenueRecovered || 5600
  const riskAmount = metricsData?.revenueAtRisk || 26000

  return (
    <div className="space-y-5 animate-in fade-in duration-150">
      {/* Reassuring Hero Status */}
      <AgentStatusHero
        activePhase={currentPhase}
        currentStepIndex={currentStepIndex}
        attentionCount={attentionCount}
      />

      {/* 4 Core Business Metric Cards (Clickable) */}
      <MetricsRail
        dynamicMetrics={metricsData}
        onNavigateToPayments={onNavigateToPayments}
      />

      {/* Revenue Breakdown Chart */}
      <RevenueChart dynamicMetrics={metricsData} />

      {/* Prominent Needs Attention Section */}
      <NeedsAttentionSection
        incidentsList={incidentsList}
        onReviewPayment={onReviewPayment}
      />

      {/* Overview Activity & Quick Access */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        <div className="lg:col-span-8">
          <LiveActivityFeed
            selectedPaymentId="pay_005"
            onRunComplete={onReload}
            incidentsList={incidentsList}
            onSelectPayment={onReviewPayment}
          />
        </div>

        {/* Right Column: AI Recovery Summary & Quick Payments */}
        <div className="lg:col-span-4 space-y-4">
          
          {/* Compact AI Recovery Summary Card */}
          <div className="p-5 bg-white border border-slate-200 rounded-2xl shadow-xs space-y-3">
            <div className="flex items-center justify-between border-b border-slate-100 pb-2.5">
              <div className="flex items-center gap-2">
                <Zap size={14} className="text-brand-600" />
                <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">AI Recovery Summary</h3>
              </div>
              <span className="text-[10px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                TODAY
              </span>
            </div>

            <div className="space-y-2 text-xs">
              <div className="flex justify-between items-center text-slate-600">
                <span>Incidents Monitored:</span>
                <span className="font-bold text-slate-900">{incidentsList?.length || 5}</span>
              </div>
              <div className="flex justify-between items-center text-slate-600">
                <span>Recovered & Verified:</span>
                <span className="font-bold text-emerald-700">
                  {(incidentsList || []).filter(i => i.recoveryStatus === 'SUCCESS' || i.status === 'RECOVERED').length}
                </span>
              </div>
              <div className="flex justify-between items-center text-slate-600">
                <span>Awaiting Operator Review:</span>
                <span className="font-bold text-amber-700">{attentionCount}</span>
              </div>
              <div className="flex justify-between items-center text-slate-600">
                <span>Stopped by Safety Policy:</span>
                <span className="font-bold text-slate-700">
                  {(incidentsList || []).filter(i => i.recoveryStatus === 'STOPPED' || i.status === 'STOPPED').length}
                </span>
              </div>

              <div className="pt-2 border-t border-slate-100 space-y-1 text-[11px]">
                <div className="flex justify-between text-emerald-700 font-bold">
                  <span>Recovered Revenue:</span>
                  <span>₹{Number(recoveredAmount).toLocaleString('en-IN')}</span>
                </div>
                <div className="flex justify-between text-rose-600 font-bold">
                  <span>Revenue at Risk:</span>
                  <span>₹{Number(riskAmount).toLocaleString('en-IN')}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Quick Payments Summary */}
          <div className="p-5 bg-white border border-slate-200 rounded-2xl shadow-xs space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">Payment Quick Access</h3>
              <button
                onClick={() => onNavigateToPayments('ALL')}
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
                    <div className="font-bold text-slate-900">₹{item.amount.toLocaleString('en-IN')}</div>
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

function PaymentsTab({ incidentsList, selectedId, onSelectId, onRunRecovery, onOpenImportModal, onNavigateToFileAnalysis, initialFilter }) {
  const selected = (incidentsList || []).find((i) => i.id === selectedId) || null

  return (
    <div className="space-y-5 animate-in fade-in duration-150">
      <IncidentTable
        incidentsList={incidentsList}
        selectedId={selectedId}
        onSelect={onSelectId}
        onOpenImportModal={onOpenImportModal}
        onNavigateToFileAnalysis={onNavigateToFileAnalysis}
        initialFilter={initialFilter}
      />

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

function AuthenticatedApp() {
  const { isAuthenticated } = useAuth()
  const [activeTab, setActiveTab] = useState('Overview')
  const [selectedIncidentId, setSelectedIncidentId] = useState('pay_005')
  const [paymentFilter, setPaymentFilter] = useState('ALL')
  const [incidentsList, setIncidentsList] = useState(fallbackIncidents)
  const [metricsData, setMetricsData] = useState(fallbackMetrics)
  const [auditLogsList, setAuditLogsList] = useState(null)
  const [currentPhase, setCurrentPhase] = useState('OBSERVING')
  const [currentStepIndex, setCurrentStepIndex] = useState(1)
  const [showImportModal, setShowImportModal] = useState(false)

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

  const handleNavigateToFilteredPayments = (filterCategory = 'ALL') => {
    setPaymentFilter(filterCategory)
    setActiveTab('Payments')
  }

  const handleRunRecoveryFromAnywhere = (paymentId) => {
    setSelectedIncidentId(paymentId)
    triggerRunPythonAgent(paymentId).then(() => reloadData())
  }

  if (!isAuthenticated) {
    return <LoginPage onLoginSuccess={() => setActiveTab('Overview')} />
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
            onNavigateToPayments={handleNavigateToFilteredPayments}
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
            onNavigateToFileAnalysis={() => setActiveTab('File Analysis')}
            initialFilter={paymentFilter}
          />
        )
      case 'File Analysis':
        return (
          <FileAnalysisWorkspace
            onNavigateToPayments={() => setActiveTab('Payments')}
            onSelectPaymentForReview={(pid) => {
              setSelectedIncidentId(pid)
              setActiveTab('Payments')
            }}
            onDataRefresh={reloadData}
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
            onNavigateToPayments={handleNavigateToFilteredPayments}
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
        incidentsList={incidentsList}
      />
      <StatusBar />

      <main className="px-4 sm:px-6 py-6 max-w-[1600px] w-full mx-auto flex-1">
        {renderTab()}
      </main>

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

export default function App() {
  return (
    <AuthProvider>
      <AuthenticatedApp />
    </AuthProvider>
  )
}
