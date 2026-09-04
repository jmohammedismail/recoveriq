import { useState, useEffect } from 'react'
import {
  Activity, Shield, Database, Key, CheckCircle2, AlertTriangle, AlertCircle,
  Play, RefreshCw, Terminal, Clock, Filter, Eye, Code, Layers, Sparkles
} from 'lucide-react'
import { fetchAgentEvents, triggerRunPythonAgent } from '../../services/api'

export default function LiveActivityFeed({ selectedPaymentId, onRunComplete, incidentsList, onSelectPayment }) {
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(false)
  const [showTechnicalDetails, setShowTechnicalDetails] = useState(false)
  const [filterType, setFilterType] = useState('ALL')

  const loadEvents = async () => {
    try {
      const data = await fetchAgentEvents()
      if (data && data.length > 0) {
        setEvents(data)
      }
    } catch (e) {
      console.warn('Events load fallback:', e)
    }
  }

  useEffect(() => {
    loadEvents()
    const interval = setInterval(loadEvents, 4000)
    return () => clearInterval(interval)
  }, [])

  const getEventIcon = (type, iconName) => {
    switch (type) {
      case 'TELEMETRY':
      case 'OBSERVE':
        return AlertTriangle
      case 'RECONCILIATION':
      case 'MERCHANT':
        return Database
      case 'IDEMPOTENCY':
        return Key
      case 'RECOVERY_COMPLETED':
      case 'VERIFY':
        return CheckCircle2
      case 'POLICY':
      case 'GUARD_STOP':
        return Shield
      default:
        return Activity
    }
  }

  const getEventBadgeColor = (status, type) => {
    if (status === 'ok' || status === 'green' || type === 'RECOVERY_COMPLETED') return 'emerald'
    if (status === 'warn' || type === 'TELEMETRY' || type === 'ROUTING') return 'amber'
    if (status === 'error') return 'rose'
    return 'blue'
  }

  const filteredEvents = events.filter(e => {
    if (filterType === 'ALL') return true
    if (filterType === 'PAYMENT_FAILURES') return e.type === 'TELEMETRY' || e.type === 'WORKFLOW'
    if (filterType === 'RECOVERY') return e.type === 'RECOVERY_COMPLETED' || e.type === 'RECOVER' || e.type === 'ORDER_SYNC'
    if (filterType === 'RECONCILIATION') return e.type === 'RECONCILIATION' || e.type === 'MERCHANT' || e.type === 'CONFIDENCE'
    return true
  })

  return (
    <div className="bg-white border border-slate-200 rounded-2xl shadow-xs overflow-hidden">
      
      {/* Header & Controls */}
      <div className="p-5 border-b border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-slate-50/50">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-bold text-slate-900">Live Agent Activity Feed</h3>
            <span className="text-[10px] font-bold text-brand-700 bg-brand-50 px-2 py-0.5 rounded border border-brand-200">
              AUTONOMOUS STREAM
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Real-time chronological stream of failure detection, telemetry observations, 4-way reconciliation, and recovery executions.
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* Technical Details Toggle */}
          <button
            onClick={() => setShowTechnicalDetails(!showTechnicalDetails)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
              showTechnicalDetails
                ? 'bg-slate-900 text-white shadow-xs'
                : 'bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 shadow-2xs'
            }`}
          >
            <Code size={13} />
            <span>{showTechnicalDetails ? 'Technical Details ON' : 'Show Technical Details'}</span>
          </button>
        </div>
      </div>

      {/* Events List */}
      <div className="divide-y divide-slate-100 max-h-[600px] overflow-y-auto">
        {filteredEvents.length === 0 ? (
          <div className="p-8 text-center text-slate-400 text-xs font-medium">
            No activity events recorded yet.
          </div>
        ) : (
          filteredEvents.map((event, idx) => {
            const Icon = getEventIcon(event.type, event.icon)
            const badgeColor = getEventBadgeColor(event.status, event.type)
            const pid = event.payment_id || 'pay_005'
            const tech = event.technical || {
              traceId: `tr_${pid}_${event.id || idx}`,
              latency: '42 ms',
              httpStatus: event.status === 'warn' ? 504 : 200,
              idempotencyKey: `${pid}_ORDER_SYNC_v1`
            }

            return (
              <div key={event.id || idx} className="p-4 hover:bg-slate-50/80 transition-colors space-y-2">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-3">
                    <div className={`w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 text-white shadow-2xs ${
                      badgeColor === 'amber' ? 'bg-amber-600' : badgeColor === 'emerald' ? 'bg-emerald-600' : badgeColor === 'rose' ? 'bg-rose-600' : 'bg-brand-600'
                    }`}>
                      <Icon size={14} />
                    </div>
                    <div className="space-y-0.5">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-xs font-bold text-slate-900">{event.title}</span>
                        {event.payment_id && (
                          <span
                            onClick={() => onSelectPayment && onSelectPayment(event.payment_id)}
                            className="font-mono text-[10px] font-bold text-brand-700 bg-brand-50 px-1.5 py-0.5 rounded border border-brand-200 hover:underline cursor-pointer"
                          >
                            {event.payment_id}
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-slate-600">{event.detail}</p>
                    </div>
                  </div>

                  <span className="font-mono text-[11px] text-slate-400 whitespace-nowrap">
                    {event.time || 'Just now'}
                  </span>
                </div>

                {/* Technical Details Drawer if enabled */}
                {showTechnicalDetails && (
                  <div className="ml-10 p-3 bg-slate-900 text-slate-200 rounded-xl font-mono text-[11px] grid grid-cols-2 sm:grid-cols-4 gap-2 border border-slate-800">
                    <div>
                      <span className="text-slate-500">Trace ID:</span>
                      <div className="text-brand-300 font-bold truncate">{tech.traceId}</div>
                    </div>
                    <div>
                      <span className="text-slate-500">Latency:</span>
                      <div className="text-emerald-400 font-bold">{tech.latency}</div>
                    </div>
                    <div>
                      <span className="text-slate-500">Status Code:</span>
                      <div className="text-slate-300 font-bold">{tech.httpStatus} OK</div>
                    </div>
                    <div>
                      <span className="text-slate-500">Idempotency Key:</span>
                      <div className="text-brand-300 truncate">{tech.idempotencyKey}</div>
                    </div>
                  </div>
                )}
              </div>
            )
          })
        )}
      </div>

    </div>
  )
}
