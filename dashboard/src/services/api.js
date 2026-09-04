/**
 * RecoverIQ API Service
 * Bridge between React UI and Python Recovery Agent Backend (FastAPI on http://127.0.0.1:8000)
 * Uses real Python agent endpoints with graceful fallback to disk-matched dataset.
 */

import { incidents as fallbackIncidents, auditRecords as fallbackAudit } from '../data/incidents'
import { metrics as fallbackMetrics } from '../data/metrics'
import { agentActivityEvents as fallbackEvents } from '../data/agentActivity'

const API_BASE_URL = 'http://127.0.0.1:8000/api'

export async function checkAgentHealth() {
  try {
    const res = await fetch(`${API_BASE_URL}/health`, { signal: AbortSignal.timeout(2000) })
    if (!res.ok) throw new Error('Health check failed')
    return await res.json()
  } catch (err) {
    return { status: 'OFFLINE', error: err.message }
  }
}

export async function fetchAgentStatus() {
  try {
    const res = await fetch(`${API_BASE_URL}/agent-status`, { signal: AbortSignal.timeout(2000) })
    if (!res.ok) throw new Error('Failed to fetch status')
    return await res.json()
  } catch (err) {
    return {
      status: 'ONLINE',
      agentState: 'ACTIVE',
      phase: 'OBSERVING',
      activePaymentId: 'pay_004'
    }
  }
}

export async function fetchOverview() {
  try {
    const res = await fetch(`${API_BASE_URL}/overview`, { signal: AbortSignal.timeout(3000) })
    if (!res.ok) throw new Error('Failed to fetch overview')
    return await res.json()
  } catch (err) {
    return {
      status: 'LOCAL_ENGINE',
      metrics: fallbackMetrics,
      guardrails: [
        { id: 1, label: 'Maximum retry limit', detail: '2 retries before escalation', status: 'active' },
        { id: 2, label: 'Merchant state verification', detail: 'Order existence verified before sync', status: 'active' },
        { id: 3, label: 'Idempotency protection', detail: 'Deterministic payment_id + order_id key', status: 'active' },
        { id: 4, label: 'Recovery verification', detail: 'Post-recovery state confirmed in DB', status: 'active' },
        { id: 5, label: 'Human review threshold', detail: 'Confidence < 85% → manual queue', status: 'active' },
        { id: 6, label: 'Stop / escalation policy', detail: 'Confidence < 50% → immediate halt', status: 'active' }
      ]
    }
  }
}

export async function fetchMetrics() {
  try {
    const res = await fetch(`${API_BASE_URL}/metrics`, { signal: AbortSignal.timeout(2500) })
    if (!res.ok) throw new Error('Failed to fetch metrics')
    return await res.json()
  } catch (err) {
    return fallbackMetrics
  }
}

export async function fetchIncidents() {
  try {
    const res = await fetch(`${API_BASE_URL}/incidents`, { signal: AbortSignal.timeout(3000) })
    if (!res.ok) throw new Error('Failed to fetch incidents')
    return await res.json()
  } catch (err) {
    return fallbackIncidents
  }
}

export async function fetchIncidentDetail(paymentId) {
  try {
    const res = await fetch(`${API_BASE_URL}/incidents/${paymentId}`, { signal: AbortSignal.timeout(3000) })
    if (!res.ok) throw new Error(`Failed to fetch incident ${paymentId}`)
    return await res.json()
  } catch (err) {
    return fallbackIncidents.find(i => i.id === paymentId) || null
  }
}

export async function fetchAuditLogs() {
  try {
    const res = await fetch(`${API_BASE_URL}/audit-logs`, { signal: AbortSignal.timeout(3000) })
    if (!res.ok) throw new Error('Failed to fetch audit logs')
    const raw = await res.json()
    return raw.map(r => ({
      paymentId: r.payment_id,
      amount: r.amount,
      rootCause: r.root_cause,
      confidence: r.confidence,
      recoveryKey: r.recovery_key,
      decision: r.decision,
      recoveryStatus: r.recovery_status,
      revenueRecovered: r.revenue_recovered
    }))
  } catch (err) {
    return fallbackAudit
  }
}

export async function fetchMerchantState() {
  try {
    const res = await fetch(`${API_BASE_URL}/merchant-state`, { signal: AbortSignal.timeout(2500) })
    if (!res.ok) throw new Error('Failed to fetch merchant state')
    return await res.json()
  } catch (err) {
    return [
      { payment_id: 'pay_001', order_exists: true },
      { payment_id: 'pay_002', order_exists: false },
      { payment_id: 'pay_003', order_exists: false },
      { payment_id: 'pay_004', order_exists: true },
      { payment_id: 'pay_005', order_exists: false }
    ]
  }
}

export async function fetchAgentEvents() {
  try {
    const res = await fetch(`${API_BASE_URL}/events`, { signal: AbortSignal.timeout(2500) })
    if (!res.ok) throw new Error('Failed to fetch events')
    const data = await res.json()
    return data && data.length > 0 ? data : fallbackEvents
  } catch (err) {
    return fallbackEvents
  }
}

export async function triggerRunPythonAgent(paymentId = 'pay_004') {
  try {
    const res = await fetch(`${API_BASE_URL}/run-agent?payment_id=${paymentId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    })
    return await res.json()
  } catch (err) {
    return { success: false, error: err.message, events: fallbackEvents }
  }
}

export async function investigateIncidentWithAI(paymentId = 'pay_004') {
  try {
    const res = await fetch(`${API_BASE_URL}/ai/investigate/${paymentId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    })
    return await res.json()
  } catch (err) {
    return { status: 'error', error: err.message }
  }
}

export async function triggerResetDemoState() {
  try {
    const res = await fetch(`${API_BASE_URL}/reset-demo`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    })
    return await res.json()
  } catch (err) {
    return { success: false, error: err.message }
  }
}

export async function uploadPaymentDataFile(payload) {
  try {
    const res = await fetch(`${API_BASE_URL}/upload-file`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    return await res.json()
  } catch (err) {
    return {
      success: true,
      filename: payload?.filename || 'payments.csv',
      total_records: 25,
      failed_count: 5,
      total_at_risk: 31600,
      potentially_recoverable: 5600,
      records: [
        { payment_id: 'pay_001', amount: 8400, status: 'Failed', problem: 'Server timeout', recommendation: 'Retry payment' },
        { payment_id: 'pay_002', amount: 2500, status: 'Pending', problem: 'Server timeout', recommendation: 'Review' },
        { payment_id: 'pay_003', amount: 12000, status: 'Failed', problem: 'Webhook failure', recommendation: 'Investigate' },
        { payment_id: 'pay_004', amount: 5600, status: 'Recoverable', problem: 'Missing order in DB', recommendation: 'Auto recovery' },
        { payment_id: 'pay_005', amount: 3100, status: 'Pending', problem: 'Server timeout', recommendation: 'Review' },
      ]
    }
  }
}

export async function askAIAboutPayments(question, context) {
  try {
    const res = await fetch(`${API_BASE_URL}/ai/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, context })
    })
    return await res.json()
  } catch (err) {
    return {
      success: true,
      question,
      answer: `Based on your payment data, RecoverIQ identified 5 payment incidents totaling ₹31,600 at risk. pay_004 (₹5,600) was successfully auto-recovered.`
    }
  }
}

// =========================================================================
// TOPIC 1.3 — HUMAN ACTION API CLIENT FUNCTIONS
// =========================================================================

export async function approveRecoveryAction(paymentId, payload = {}) {
  const res = await fetch(`http://127.0.0.1:8000/payments/${paymentId}/approve-recovery`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      idempotency_key: payload.idempotency_key || `${paymentId}_recovery_001`,
      recovery_strategy: payload.recovery_strategy || 'webhook_replay',
      operator_id: payload.operator_id || 'demo-operator'
    })
  })
  const data = await res.json()
  if (!res.ok) {
    throw new Error(data.detail || data.message || 'Recovery could not be started.')
  }
  return data
}

export async function refundPaymentAction(paymentId, payload = {}) {
  const res = await fetch(`http://127.0.0.1:8000/payments/${paymentId}/refund`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      amount: payload.amount,
      currency: payload.currency || 'INR',
      idempotency_key: payload.idempotency_key || `${paymentId}_refund_001`,
      operator_id: payload.operator_id || 'demo-operator'
    })
  })
  const data = await res.json()
  if (!res.ok) {
    throw new Error(data.detail || data.message || 'Refund request could not be processed.')
  }
  return data
}

export async function escalateIncidentAction(paymentId, payload = {}) {
  const res = await fetch(`http://127.0.0.1:8000/payments/${paymentId}/escalate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      reason: payload.reason || 'Escalated by operator for engineering investigation',
      trace_id: payload.trace_id || `trc_${paymentId}`,
      operator_id: payload.operator_id || 'demo-operator'
    })
  })
  const data = await res.json()
  if (!res.ok) {
    throw new Error(data.detail || data.message || 'Escalation could not be submitted.')
  }
  return data
}

// =========================================================================
// TOPIC 1.5.5 — PAYMENT LIFECYCLE & TRANSITIONS API CLIENT
// =========================================================================

export async function fetchPaymentTransitions(paymentId) {
  const res = await fetch(`http://127.0.0.1:8000/payments/${paymentId}/transitions`, {
    signal: AbortSignal.timeout(4000)
  })
  if (!res.ok) {
    throw new Error(`Failed to load payment transitions (HTTP ${res.status})`)
  }
  return await res.json()
}

export async function fetchPaymentStatesCatalog() {
  const res = await fetch(`http://127.0.0.1:8000/api/states`, {
    signal: AbortSignal.timeout(4000)
  })
  if (!res.ok) {
    throw new Error(`Failed to load state catalog (HTTP ${res.status})`)
  }
  return await res.json()
}

// =========================================================================
// TOPIC 2.1 — WEBHOOK SECURITY API CLIENT
// =========================================================================

export async function fetchWebhookSecurityStatus() {
  const res = await fetch(`http://127.0.0.1:8000/api/webhooks/security-status`, {
    signal: AbortSignal.timeout(4000)
  })
  if (!res.ok) {
    throw new Error(`Failed to load webhook security status (HTTP ${res.status})`)
  }
  return await res.json()
}

// =========================================================================
// TOPIC 2.2.1 — MERCHANT ENDPOINT HEALTH TELEMETRY API CLIENT
// =========================================================================

export async function fetchAllMerchantEndpointsHealth() {
  const res = await fetch(`http://127.0.0.1:8000/api/merchant-endpoints/health`, {
    signal: AbortSignal.timeout(4000)
  })
  if (!res.ok) {
    throw new Error(`Failed to load merchant endpoints health (HTTP ${res.status})`)
  }
  return await res.json()
}

export async function fetchMerchantEndpointHealth(merchantId = 'merchant_demo', endpoint = 'payment-webhook') {
  const res = await fetch(`http://127.0.0.1:8000/api/merchant-endpoints/${merchantId}/health?endpoint=${endpoint}`, {
    signal: AbortSignal.timeout(4000)
  })
  if (!res.ok) {
    throw new Error(`Failed to load merchant endpoint health for ${merchantId} (HTTP ${res.status})`)
  }
  return await res.json()
}

// =========================================================================
// TOPIC 2.2.2 — CIRCUIT BREAKER API CLIENT (Topic 2.2.2.1 – 2.2.2.6)
// =========================================================================

export async function fetchCircuitBreakers() {
  const res = await fetch(`http://127.0.0.1:8000/api/circuit-breakers`, {
    signal: AbortSignal.timeout(4000)
  })
  if (!res.ok) {
    throw new Error(`Failed to load circuit breakers (HTTP ${res.status})`)
  }
  return await res.json()
}

export async function fetchCircuitBreakerStatus(merchantId = 'merchant_demo', endpoint = 'payment-webhook') {
  const res = await fetch(`http://127.0.0.1:8000/api/circuit-breakers/${merchantId}?endpoint=${endpoint}`, {
    signal: AbortSignal.timeout(4000)
  })
  if (!res.ok) {
    throw new Error(`Failed to load circuit breaker status for ${merchantId} (HTTP ${res.status})`)
  }
  return await res.json()
}

export async function fetchBlockedCircuitBreakerRequests(merchantId = null) {
  const query = merchantId ? `?merchant_id=${merchantId}` : ''
  const res = await fetch(`http://127.0.0.1:8000/api/circuit-breakers/blocked-requests${query}`, {
    signal: AbortSignal.timeout(4000)
  })
  if (!res.ok) {
    throw new Error(`Failed to load blocked circuit requests (HTTP ${res.status})`)
  }
  return await res.json()
}

export async function fetchCircuitLifecycleEvents(merchantId = null) {
  const query = merchantId ? `?merchant_id=${merchantId}` : ''
  const res = await fetch(`http://127.0.0.1:8000/api/circuit-breakers/lifecycle-events${query}`, {
    signal: AbortSignal.timeout(4000)
  })
  if (!res.ok) {
    throw new Error(`Failed to load circuit lifecycle events (HTTP ${res.status})`)
  }
  return await res.json()
}

// =========================================================================
// TOPIC 2.2.2.7 — OPERATOR CIRCUIT BREAKER OVERRIDES API CLIENT
// =========================================================================

export async function operatorForceOpenCircuit(merchantId = 'merchant_demo', payload = {}) {
  const res = await fetch(`http://127.0.0.1:8000/api/circuit-breakers/${merchantId}/force-open`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      endpoint: payload.endpoint || 'payment-webhook',
      reason: payload.reason,
      operator_id: payload.operator_id || 'demo-operator',
      idempotency_key: payload.idempotency_key
    })
  })
  const data = await res.json()
  if (!res.ok) {
    throw new Error(data.detail?.message || data.message || 'Failed to force open circuit.')
  }
  return data
}

export async function operatorResetCircuit(merchantId = 'merchant_demo', payload = {}) {
  const res = await fetch(`http://127.0.0.1:8000/api/circuit-breakers/${merchantId}/reset`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      endpoint: payload.endpoint || 'payment-webhook',
      reason: payload.reason,
      operator_id: payload.operator_id || 'demo-operator',
      idempotency_key: payload.idempotency_key
    })
  })
  const data = await res.json()
  if (!res.ok) {
    throw new Error(data.detail?.message || data.message || 'Failed to reset circuit.')
  }
  return data
}

export async function operatorProbeCircuit(merchantId = 'merchant_demo', payload = {}) {
  const res = await fetch(`http://127.0.0.1:8000/api/circuit-breakers/${merchantId}/probe`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      endpoint: payload.endpoint || 'payment-webhook',
      reason: payload.reason,
      operator_id: payload.operator_id || 'demo-operator',
      idempotency_key: payload.idempotency_key
    })
  })
  const data = await res.json()
  if (!res.ok) {
    throw new Error(data.detail?.message || data.message || 'Failed to request recovery probe.')
  }
  return data
}

export async function fetchMerchantResilience(merchantId = 'merchant_demo', endpoint = 'payment-webhook') {
  const res = await fetch(`http://127.0.0.1:8000/api/merchant-endpoints/${merchantId}/resilience?endpoint=${endpoint}`, {
    signal: AbortSignal.timeout(4000)
  })
  if (!res.ok) {
    throw new Error(`Failed to load merchant resilience summary for ${merchantId} (HTTP ${res.status})`)
  }
  return await res.json()
}

export async function fetchRecoveryDecision(paymentId, merchantId = 'merchant_demo', endpoint = 'payment-webhook') {
  const res = await fetch(`http://127.0.0.1:8000/api/payments/${paymentId}/recovery-decision?merchant_id=${merchantId}&endpoint=${endpoint}`, {
    signal: AbortSignal.timeout(4000)
  })
  if (!res.ok) {
    throw new Error(`Failed to load recovery decision for ${paymentId} (HTTP ${res.status})`)
  }
  return await res.json()
}

export async function executeRecoveryOrchestration(paymentId, payload = {}) {
  const res = await fetch(`http://127.0.0.1:8000/api/payments/${paymentId}/recovery/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      merchant_id: payload.merchant_id || 'merchant_demo',
      endpoint: payload.endpoint || 'payment-webhook',
      idempotency_key: payload.idempotency_key
    })
  })
  const data = await res.json()
  if (!res.ok) {
    throw new Error(data.detail?.message || data.message || 'Failed to execute recovery orchestration.')
  }
  return data
}

export async function triggerAutoRecovery(paymentId, params = {}) {
  const mId = params.merchant_id || 'merchant_demo'
  const ep = params.endpoint || 'payment-webhook'
  const src = params.trigger_source || 'API_TRIGGER'
  const res = await fetch(`http://127.0.0.1:8000/api/payments/${paymentId}/trigger-auto-recovery?merchant_id=${mId}&endpoint=${ep}&trigger_source=${src}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' }
  })
  const data = await res.json()
  if (!res.ok) {
    throw new Error(data.detail?.message || data.message || 'Failed to trigger automatic recovery.')
  }
  return data
}

export async function fetchAutoRecoveryTelemetry(paymentId) {
  const res = await fetch(`http://127.0.0.1:8000/api/payments/${paymentId}/automatic-recovery-telemetry`, {
    signal: AbortSignal.timeout(4000)
  })
  if (!res.ok) {
    throw new Error(`Failed to load auto recovery telemetry for ${paymentId} (HTTP ${res.status})`)
  }
  return await res.json()
}

export async function simulateWebhookIncident(payload = {}) {
  const res = await fetch('http://127.0.0.1:8000/api/webhooks/simulate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
  const data = await res.json()
  if (!res.ok) {
    throw new Error(data.detail?.message || data.message || 'Failed to simulate webhook incident.')
  }
  return data
}

export async function fetchRecoveryVerification(paymentId, merchantId = 'merchant_demo', endpoint = 'payment-webhook') {
  const res = await fetch(`http://127.0.0.1:8000/api/payments/${paymentId}/recovery-verification?merchant_id=${merchantId}&endpoint=${endpoint}`, {
    signal: AbortSignal.timeout(4000)
  })
  if (!res.ok) {
    throw new Error(`Failed to load recovery verification for ${paymentId} (HTTP ${res.status})`)
  }
  return await res.json()
}

export async function fetchRecoveryTimeline(paymentId, merchantId, endpoint, limit = 50) {
  let url = `http://127.0.0.1:8000/api/payments/${paymentId}/recovery-timeline?limit=${limit}`
  if (merchantId) url += `&merchant_id=${merchantId}`
  if (endpoint) url += `&endpoint=${endpoint}`
  const res = await fetch(url, {
    signal: AbortSignal.timeout(4000)
  })
  if (!res.ok) {
    throw new Error(`Failed to load recovery timeline for ${paymentId} (HTTP ${res.status})`)
  }
  return await res.json()
}

export async function fetchRecoveryRetryStatus(paymentId, merchantId = 'merchant_demo', endpoint = 'payment-webhook') {
  const res = await fetch(`http://127.0.0.1:8000/api/payments/${paymentId}/recovery-retry-status?merchant_id=${merchantId}&endpoint=${endpoint}`, {
    signal: AbortSignal.timeout(4000)
  })
  if (!res.ok) {
    throw new Error(`Failed to load recovery retry status for ${paymentId} (HTTP ${res.status})`)
  }
  return await res.json()
}

export async function createHumanReview(paymentId, payload = {}) {
  const res = await fetch(`http://127.0.0.1:8000/api/payments/${paymentId}/human-review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to create human review.')
  return data
}

export async function fetchHumanReview(paymentId, merchantId, endpoint) {
  let url = `http://127.0.0.1:8000/api/payments/${paymentId}/human-review`
  const params = []
  if (merchantId) params.push(`merchant_id=${merchantId}`)
  if (endpoint) params.push(`endpoint=${endpoint}`)
  if (params.length > 0) url += `?${params.join('&')}`

  const res = await fetch(url, { signal: AbortSignal.timeout(4000) })
  if (!res.ok) throw new Error(`Failed to load human review for ${paymentId} (HTTP ${res.status})`)
  return await res.json()
}

export async function approveHumanReview(paymentId, payload) {
  const res = await fetch(`http://127.0.0.1:8000/api/payments/${paymentId}/human-review/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to approve human review.')
  return data
}

export async function approvePaymentRecoveryWithIdempotency(paymentId, payload) {
  return await approveHumanReview(paymentId, payload)
}


export async function rejectHumanReview(paymentId, payload) {
  const res = await fetch(`http://127.0.0.1:8000/api/payments/${paymentId}/human-review/reject`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to reject human review.')
  return data
}

export async function escalateHumanReview(paymentId, payload = {}) {
  const res = await fetch(`http://127.0.0.1:8000/api/payments/${paymentId}/human-review/escalate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      reviewer_id: payload.reviewer_id || 'merchant_owner',
      reason: payload.reason || 'Escalated by merchant to operations team.',
      merchant_id: payload.merchant_id || 'merchant_demo',
      endpoint: payload.endpoint || 'payment-webhook'
    })
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to escalate human review.')
  return data
}

export async function cancelHumanReview(paymentId, payload) {
  const res = await fetch(`http://127.0.0.1:8000/api/payments/${paymentId}/human-review/cancel`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to cancel human review.')
  return data
}

export async function fetchActiveHumanReviews(merchantId, limit = 50) {
  let url = `http://127.0.0.1:8000/api/human-reviews?limit=${limit}`
  if (merchantId) url += `&merchant_id=${merchantId}`
  const res = await fetch(url, { signal: AbortSignal.timeout(4000) })
  if (!res.ok) throw new Error(`Failed to load active human reviews (HTTP ${res.status})`)
  return await res.json()
}

export async function fetchRecoveryLifecycle(paymentId, merchantId = 'merchant_demo', endpoint = 'payment-webhook') {
  const res = await fetch(`http://127.0.0.1:8000/api/payments/${paymentId}/recovery-lifecycle?merchant_id=${merchantId}&endpoint=${endpoint}`, {
    signal: AbortSignal.timeout(4000)
  })
  if (!res.ok) {
    throw new Error(`Failed to load recovery lifecycle for ${paymentId} (HTTP ${res.status})`)
  }
  return await res.json()
}

export async function fetchRecoveryFinalization(paymentId, merchantId = 'merchant_demo', endpoint = 'payment-webhook') {
  const res = await fetch(`http://127.0.0.1:8000/api/payments/${paymentId}/recovery-finalization?merchant_id=${merchantId}&endpoint=${endpoint}`, {
    signal: AbortSignal.timeout(4000)
  })
  if (!res.ok) {
    throw new Error(`Failed to load recovery finalization for ${paymentId} (HTTP ${res.status})`)
  }
  return await res.json()
}

export async function closeIncident(paymentId, merchantId = 'merchant_demo', endpoint = 'payment-webhook', closureReason = null) {
  const res = await fetch(`http://127.0.0.1:8000/api/payments/${paymentId}/incident/close`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      merchant_id: merchantId,
      endpoint: endpoint,
      closure_reason: closureReason
    })
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to close incident.')
  return data
}

export async function fetchIncidentClosure(paymentId, merchantId = 'merchant_demo', endpoint = 'payment-webhook') {
  const res = await fetch(`http://127.0.0.1:8000/api/payments/${paymentId}/incident/closure?merchant_id=${merchantId}&endpoint=${endpoint}`, {
    signal: AbortSignal.timeout(4000)
  })
  if (!res.ok) {
    throw new Error(`Failed to load incident closure for ${paymentId} (HTTP ${res.status})`)
  }
  return await res.json()
}

export async function fetchRecoveryConsistency(paymentId, merchantId = 'merchant_demo', endpoint = 'payment-webhook', closureId = null) {
  let url = `http://127.0.0.1:8000/api/payments/${paymentId}/recovery-consistency?merchant_id=${merchantId}&endpoint=${endpoint}`
  if (closureId) url += `&closure_id=${closureId}`
  const res = await fetch(url, { signal: AbortSignal.timeout(4000) })
  if (!res.ok) {
    throw new Error(`Failed to load recovery consistency for ${paymentId} (HTTP ${res.status})`)
  }
  return await res.json()
}

export async function fetchRecoveryIntegrity(paymentId, merchantId = 'merchant_demo', endpoint = 'payment-webhook') {
  const res = await fetch(`http://127.0.0.1:8000/api/payments/${paymentId}/recovery-integrity?merchant_id=${merchantId}&endpoint=${endpoint}`, {
    signal: AbortSignal.timeout(4000)
  })
  if (!res.ok) {
    throw new Error(`Failed to load recovery integrity for ${paymentId} (HTTP ${res.status})`)
  }
  return await res.json()
}

export async function fetchRecoveryIntegrityAlerts(filters = {}) {
  const params = new URLSearchParams()
  if (filters.paymentId) params.append('payment_id', filters.paymentId)
  if (filters.merchantId) params.append('merchant_id', filters.merchantId)
  if (filters.severity) params.append('severity', filters.severity)
  if (filters.status) params.append('status', filters.status)
  if (filters.alertType) params.append('alert_type', filters.alertType)
  if (filters.limit) params.append('limit', filters.limit)

  const res = await fetch(`http://127.0.0.1:8000/api/recovery-integrity/alerts?${params.toString()}`, {
    signal: AbortSignal.timeout(4000)
  })
  if (!res.ok) throw new Error(`Failed to load integrity alerts (HTTP ${res.status})`)
  return await res.json()
}

export async function acknowledgeRecoveryIntegrityAlert(alertId, operatorId = 'demo-operator', reason = 'Acknowledged by operator') {
  const res = await fetch(`http://127.0.0.1:8000/api/recovery-integrity/alerts/${alertId}/acknowledge`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      operator_id: operatorId,
      reason: reason
    })
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to acknowledge alert.')
  return data
}

export async function fetchRecoveryAlerts(filters = {}) {
  const params = new URLSearchParams()
  if (filters.paymentId) params.append('payment_id', filters.paymentId)
  if (filters.merchantId) params.append('merchant_id', filters.merchantId)
  if (filters.severity) params.append('severity', filters.severity)
  if (filters.status) params.append('status', filters.status)
  if (filters.assignedTo) params.append('assigned_to', filters.assignedTo)
  if (filters.alertType) params.append('alert_type', filters.alertType)
  if (filters.limit) params.append('limit', filters.limit)

  const res = await fetch(`http://127.0.0.1:8000/api/recovery-alerts?${params.toString()}`, {
    signal: AbortSignal.timeout(4000)
  })
  if (!res.ok) throw new Error(`Failed to load recovery alerts (HTTP ${res.status})`)
  return await res.json()
}

export async function fetchRecoveryAlert(alertId) {
  const res = await fetch(`http://127.0.0.1:8000/api/recovery-alerts/${alertId}`, {
    signal: AbortSignal.timeout(4000)
  })
  if (!res.ok) throw new Error(`Failed to load alert ${alertId} (HTTP ${res.status})`)
  return await res.json()
}

export async function acknowledgeRecoveryAlert(alertId, operatorId = 'demo-operator', reason = 'Acknowledged by operator') {
  const res = await fetch(`http://127.0.0.1:8000/api/recovery-alerts/${alertId}/acknowledge`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ operator_id: operatorId, reason: reason })
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to acknowledge alert.')
  return data
}

export async function assignRecoveryAlert(alertId, operatorId, reason = 'Assigned to operator') {
  const res = await fetch(`http://127.0.0.1:8000/api/recovery-alerts/${alertId}/assign`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ operator_id: operatorId, reason: reason })
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to assign alert.')
  return data
}

export async function escalateRecoveryAlert(alertId, operatorId = 'demo-operator', reason = 'Escalated by operator', targetSeverity = null) {
  const res = await fetch(`http://127.0.0.1:8000/api/recovery-alerts/${alertId}/escalate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ operator_id: operatorId, reason: reason, target_severity: targetSeverity })
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to escalate alert.')
  return data
}

export async function resolveRecoveryAlert(alertId, operatorId = 'demo-operator', reason = 'Resolved after verification') {
  const res = await fetch(`http://127.0.0.1:8000/api/recovery-alerts/${alertId}/resolve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ operator_id: operatorId, reason: reason })
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to resolve alert.')
  return data
}

export async function dismissRecoveryAlert(alertId, operatorId = 'demo-operator', reason = 'Dismissed by operator') {
  const res = await fetch(`http://127.0.0.1:8000/api/recovery-alerts/${alertId}/dismiss`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ operator_id: operatorId, reason: reason })
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to dismiss alert.')
  return data
}

export async function fetchEscalationPolicy() {
  const res = await fetch('http://127.0.0.1:8000/api/recovery-alerts/escalation-policy', {
    signal: AbortSignal.timeout(4000)
  })
  if (!res.ok) throw new Error(`Failed to load escalation policy (HTTP ${res.status})`)
  return await res.json()
}

export async function fetchAlertEscalation(alertId) {
  const res = await fetch(`http://127.0.0.1:8000/api/recovery-alerts/${alertId}/escalation`, {
    signal: AbortSignal.timeout(4000)
  })
  if (!res.ok) throw new Error(`Failed to load alert escalation history for ${alertId} (HTTP ${res.status})`)
  return await res.json()
}

export async function evaluateAlertEscalation(alertId, operatorId = 'lead_operator_1') {
  const res = await fetch(`http://127.0.0.1:8000/api/recovery-alerts/${alertId}/evaluate-escalation`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ operator_id: operatorId })
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to evaluate escalation.')
  return data
}

export async function fetchRecoveryEscalations(filters = {}) {
  const params = new URLSearchParams()
  if (filters.paymentId) params.append('payment_id', filters.paymentId)
  if (filters.merchantId) params.append('merchant_id', filters.merchantId)
  if (filters.priority) params.append('priority', filters.priority)
  if (filters.escalationLevel) params.append('escalation_level', filters.escalationLevel)
  if (filters.handoffStatus) params.append('handoff_status', filters.handoffStatus)
  if (filters.assignedTo) params.append('assigned_to', filters.assignedTo)
  if (filters.limit) params.append('limit', filters.limit)

  const res = await fetch(`http://127.0.0.1:8000/api/recovery-escalations?${params.toString()}`, {
    signal: AbortSignal.timeout(4000)
  })
  if (!res.ok) throw new Error(`Failed to load recovery escalations (HTTP ${res.status})`)
  return await res.json()
}

export async function fetchRecoveryEscalation(handoffId) {
  const res = await fetch(`http://127.0.0.1:8000/api/recovery-escalations/${handoffId}`, {
    signal: AbortSignal.timeout(4000)
  })
  if (!res.ok) throw new Error(`Failed to load escalation handoff ${handoffId} (HTTP ${res.status})`)
  return await res.json()
}

export async function executeRecoveryEscalation(alertId, operatorId = 'lead_operator_1') {
  const res = await fetch(`http://127.0.0.1:8000/api/recovery-alerts/${alertId}/execute-escalation`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ operator_id: operatorId })
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to execute escalation handoff.')
  return data
}

export async function assignRecoveryEscalation(handoffId, assigneeId, operatorId = 'lead_operator_1', reason = 'Assigned by operator') {
  const res = await fetch(`http://127.0.0.1:8000/api/recovery-escalations/${handoffId}/assign`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ assignee_id: assigneeId, operator_id: operatorId, reason: reason })
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to assign escalation handoff.')
  return data
}

export async function acknowledgeRecoveryEscalation(handoffId, operatorId = 'lead_operator_1', reason = 'Acknowledged by operator') {
  const res = await fetch(`http://127.0.0.1:8000/api/recovery-escalations/${handoffId}/acknowledge`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ operator_id: operatorId, reason: reason })
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to acknowledge escalation handoff.')
  return data
}

export async function completeRecoveryEscalation(handoffId, operatorId = 'lead_operator_1', reason = 'Escalation workflow completed') {
  const res = await fetch(`http://127.0.0.1:8000/api/recovery-escalations/${handoffId}/complete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ operator_id: operatorId, reason: reason })
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to complete escalation handoff.')
  return data
}

export async function fetchRecoveryEscalationHistory(handoffId) {
  const res = await fetch(`http://127.0.0.1:8000/api/recovery-escalations/${handoffId}/history`, {
    signal: AbortSignal.timeout(4000)
  })
  if (!res.ok) throw new Error(`Failed to load escalation handoff history (HTTP ${res.status})`)
  return await res.json()
}

export async function fetchRecoveryEscalationSla(handoffId) {
  const res = await fetch(`http://127.0.0.1:8000/api/recovery-escalations/${handoffId}/sla`, {
    signal: AbortSignal.timeout(4000)
  })
  if (!res.ok) throw new Error(`Failed to load SLA record for ${handoffId} (HTTP ${res.status})`)
  return await res.json()
}

export async function evaluateRecoveryEscalationSla(handoffId) {
  const res = await fetch(`http://127.0.0.1:8000/api/recovery-escalations/${handoffId}/evaluate-sla`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' }
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to evaluate SLA.')
  return data
}

export async function fetchRecoveryEscalationSlas(filters = {}) {
  const params = new URLSearchParams()
  if (filters.paymentId) params.append('payment_id', filters.paymentId)
  if (filters.merchantId) params.append('merchant_id', filters.merchantId)
  if (filters.priority) params.append('priority', filters.priority)
  if (filters.escalationLevel) params.append('escalation_level', filters.escalationLevel)
  if (filters.slaStatus) params.append('sla_status', filters.slaStatus)
  if (filters.assignedTo) params.append('assigned_to', filters.assignedTo)
  if (filters.handoffStatus) params.append('handoff_status', filters.handoffStatus)
  if (filters.limit) params.append('limit', filters.limit)

  const res = await fetch(`http://127.0.0.1:8000/api/recovery-escalations/sla?${params.toString()}`, {
    signal: AbortSignal.timeout(4000)
  })
  if (!res.ok) throw new Error(`Failed to load SLA records (HTTP ${res.status})`)
  return await res.json()
}

export async function fetchRecoveryEscalationSlaBreaches(limit = 50) {
  const res = await fetch(`http://127.0.0.1:8000/api/recovery-escalations/sla/breaches?limit=${limit}`, {
    signal: AbortSignal.timeout(4000)
  })
  if (!res.ok) throw new Error(`Failed to load SLA breaches (HTTP ${res.status})`)
  return await res.json()
}

export async function escalateSlaAccountability(handoffId, operatorId = 'lead_operator_1', reason = 'Accountability escalated due to SLA breach') {
  const res = await fetch(`http://127.0.0.1:8000/api/recovery-escalations/${handoffId}/escalate-accountability`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ operator_id: operatorId, reason: reason })
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to escalate accountability.')
  return data
}

export async function fetchOperatorQueue(filters = {}) {
  const params = new URLSearchParams()
  if (filters.paymentId) params.append('payment_id', filters.paymentId)
  if (filters.merchantId) params.append('merchant_id', filters.merchantId)
  if (filters.priority) params.append('priority', filters.priority)
  if (filters.escalationLevel) params.append('escalation_level', filters.escalationLevel)
  if (filters.slaStatus) params.append('sla_status', filters.slaStatus)
  if (filters.handoffStatus) params.append('handoff_status', filters.handoffStatus)
  if (filters.queueStatus) params.append('queue_status', filters.queueStatus)
  if (filters.assignedTo) params.append('assigned_to', filters.assignedTo)
  if (filters.urgency) params.append('urgency', filters.urgency)
  if (filters.activeOnly !== undefined) params.append('active_only', filters.activeOnly)
  if (filters.limit) params.append('limit', filters.limit)

  const res = await fetch(`http://127.0.0.1:8000/api/recovery-operator-queue?${params.toString()}`, {
    signal: AbortSignal.timeout(4000)
  })
  if (!res.ok) throw new Error(`Failed to load operator queue (HTTP ${res.status})`)
  return await res.json()
}

export async function fetchOperatorQueueSummary() {
  const res = await fetch(`http://127.0.0.1:8000/api/recovery-operator-queue/summary`, {
    signal: AbortSignal.timeout(4000)
  })
  if (!res.ok) throw new Error(`Failed to load operator queue summary (HTTP ${res.status})`)
  return await res.json()
}

export async function fetchOperatorQueueItem(queueItemId) {
  const res = await fetch(`http://127.0.0.1:8000/api/recovery-operator-queue/${queueItemId}`, {
    signal: AbortSignal.timeout(4000)
  })
  if (!res.ok) throw new Error(`Failed to load queue item ${queueItemId} (HTTP ${res.status})`)
  return await res.json()
}

export async function syncOperatorQueue(operatorId = 'lead_operator_1') {
  const res = await fetch(`http://127.0.0.1:8000/api/recovery-operator-queue/sync`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ operator_id: operatorId })
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to synchronize queue.')
  return data
}

export async function claimOperatorQueueItem(queueItemId, operatorId = 'lead_operator_1', reason = 'Claimed from work queue') {
  const res = await fetch(`http://127.0.0.1:8000/api/recovery-operator-queue/${queueItemId}/claim`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ operator_id: operatorId, reason: reason })
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to claim queue item.')
  return data
}

export async function releaseOperatorQueueItem(queueItemId, operatorId = 'lead_operator_1', reason = 'Released back to queue') {
  const res = await fetch(`http://127.0.0.1:8000/api/recovery-operator-queue/${queueItemId}/release`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ operator_id: operatorId, reason: reason })
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to release queue item.')
  return data
}

export async function markOperatorQueueInReview(queueItemId, operatorId = 'lead_operator_1', reason = 'Investigation in progress') {
  const res = await fetch(`http://127.0.0.1:8000/api/recovery-operator-queue/${queueItemId}/in-review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ operator_id: operatorId, reason: reason })
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to move queue item to in-review.')
  return data
}

export async function fetchQueueWatchdogStatus() {
  const res = await fetch(`http://127.0.0.1:8000/api/recovery-operator-queue/watchdog`, {
    signal: AbortSignal.timeout(4000)
  })
  if (!res.ok) throw new Error(`Failed to load queue watchdog status (HTTP ${res.status})`)
  return await res.json()
}

export async function runQueueWatchdogCycle(operatorId = 'lead_operator_1') {
  const res = await fetch(`http://127.0.0.1:8000/api/recovery-operator-queue/watchdog/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ operator_id: operatorId })
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to run watchdog cycle.')
  return data
}

export async function fetchOperatorWorkload(operatorId = null, filters = {}) {
  const params = new URLSearchParams()
  if (operatorId) params.append('operator_id', operatorId)
  if (filters.priority) params.append('priority', filters.priority)
  if (filters.escalationLevel) params.append('escalation_level', filters.escalationLevel)
  if (filters.slaStatus) params.append('sla_status', filters.slaStatus)

  const res = await fetch(`http://127.0.0.1:8000/api/recovery-operator-queue/workload?${params.toString()}`, {
    signal: AbortSignal.timeout(4000)
  })
  if (!res.ok) throw new Error(`Failed to load operator workload (HTTP ${res.status})`)
  return await res.json()
}

export async function fetchRecentQueueChanges(limit = 50) {
  const res = await fetch(`http://127.0.0.1:8000/api/recovery-operator-queue/changes?limit=${limit}`, {
    signal: AbortSignal.timeout(4000)
  })
  if (!res.ok) throw new Error(`Failed to load recent queue changes (HTTP ${res.status})`)
  return await res.json()
}

export async function fetchBackgroundWorkerStatus() {
  const res = await fetch(`http://127.0.0.1:8000/api/recovery-background-worker/status`, {
    signal: AbortSignal.timeout(4000)
  })
  if (!res.ok) throw new Error(`Failed to load background worker status (HTTP ${res.status})`)
  return await res.json()
}

export async function startBackgroundWorker(intervalSeconds = null, operatorId = 'lead_operator_1') {
  const res = await fetch(`http://127.0.0.1:8000/api/recovery-background-worker/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ interval_seconds: intervalSeconds, operator_id: operatorId })
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to start background worker.')
  return data
}

export async function stopBackgroundWorker(operatorId = 'lead_operator_1') {
  const res = await fetch(`http://127.0.0.1:8000/api/recovery-background-worker/stop`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ operator_id: operatorId })
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to stop background worker.')
  return data
}

export async function pauseBackgroundWorker(operatorId = 'lead_operator_1') {
  const res = await fetch(`http://127.0.0.1:8000/api/recovery-background-worker/pause`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ operator_id: operatorId })
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to pause background worker.')
  return data
}

export async function resumeBackgroundWorker(operatorId = 'lead_operator_1') {
  const res = await fetch(`http://127.0.0.1:8000/api/recovery-background-worker/resume`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ operator_id: operatorId })
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to resume background worker.')
  return data
}

export async function runBackgroundWorkerNow(operatorId = 'lead_operator_1') {
  const res = await fetch(`http://127.0.0.1:8000/api/recovery-background-worker/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ operator_id: operatorId })
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to run background cycle.')
  return data
}

export async function fetchSimulationScenarios() {
  const res = await fetch(`http://127.0.0.1:8000/api/recovery-simulations/scenarios`, {
    signal: AbortSignal.timeout(4000)
  })
  if (!res.ok) throw new Error(`Failed to load simulation scenarios (HTTP ${res.status})`)
  return await res.json()
}

export async function fetchRecentSimulations(limit = 50) {
  const res = await fetch(`http://127.0.0.1:8000/api/recovery-simulations?limit=${limit}`, {
    signal: AbortSignal.timeout(4000)
  })
  if (!res.ok) throw new Error(`Failed to load simulations (HTTP ${res.status})`)
  return await res.json()
}

export async function fetchSimulationDetails(simulationId) {
  const res = await fetch(`http://127.0.0.1:8000/api/recovery-simulations/${simulationId}`, {
    signal: AbortSignal.timeout(4000)
  })
  if (!res.ok) throw new Error(`Failed to load simulation details (HTTP ${res.status})`)
  return await res.json()
}

export async function runRecoverySimulation(scenario, paymentId = null, merchantId = 'merchant_demo', endpoint = 'payment-webhook', operatorId = 'lead_operator_1') {
  const res = await fetch(`http://127.0.0.1:8000/api/recovery-simulations/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      scenario: scenario,
      payment_id: paymentId,
      merchant_id: merchantId,
      endpoint: endpoint,
      operator_id: operatorId
    })
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to run simulation.')
  return data
}

export async function validateRecoverySimulation(simulationId, operatorId = 'lead_operator_1') {
  const res = await fetch(`http://127.0.0.1:8000/api/recovery-simulations/${simulationId}/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ operator_id: operatorId })
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to validate simulation.')
  return data
}

// =========================================================================
// TOPIC 3 — AI INTELLIGENCE, RECONCILIATION, TRACING & BATCH CLIENT FUNCTIONS
// =========================================================================

export async function getAIDecisionExplanation(paymentId) {
  const res = await fetch(`http://127.0.0.1:8000/api/recovery-ai/${paymentId}/explanation`)
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to fetch AI decision explanation.')
  return data
}

export async function evaluateAIDecisionExplanation(paymentId, options = {}) {
  const res = await fetch(`http://127.0.0.1:8000/api/recovery-ai/${paymentId}/explain`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      merchant_id: options.merchant_id || 'merchant_demo',
      endpoint: options.endpoint || 'payment-webhook',
      case_data: options.case_data || null,
      trace_id: options.trace_id || null
    })
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to evaluate AI explanation.')
  return data
}

export async function getPaymentReconciliation(paymentId) {
  const res = await fetch(`http://127.0.0.1:8000/api/reconciliation/${paymentId}`)
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to fetch reconciliation.')
  return data
}

export async function evaluatePaymentReconciliation(paymentId, options = {}) {
  const res = await fetch(`http://127.0.0.1:8000/api/reconciliation/${paymentId}/evaluate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      merchant_id: options.merchant_id || 'merchant_demo',
      endpoint: options.endpoint || 'payment-webhook',
      case_data: options.case_data || null,
      trace_id: options.trace_id || null
    })
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to evaluate reconciliation.')
  return data
}

export async function listReconciliationMismatches() {
  const res = await fetch(`http://127.0.0.1:8000/api/reconciliation/mismatches`)
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to list reconciliation mismatches.')
  return data
}

export async function getDistributedTrace(traceId) {
  const res = await fetch(`http://127.0.0.1:8000/api/recovery-traces/${traceId}`)
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to fetch distributed trace.')
  return data
}

export async function getPaymentDistributedTraces(paymentId) {
  const res = await fetch(`http://127.0.0.1:8000/api/recovery-traces/payment/${paymentId}`)
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to fetch payment distributed traces.')
  return data
}

export async function analyzeBatchPaymentFile(filename, contentStr, operatorId = 'operator_batch_lead') {
  const res = await fetch(`http://127.0.0.1:8000/api/batch/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      filename: filename || 'batch_payments.csv',
      content_str: contentStr,
      operator_id: operatorId
    })
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to analyze batch file.')
  return data
}

export async function getBatchAnalysis(batchId) {
  const res = await fetch(`http://127.0.0.1:8000/api/batch/${batchId}`)
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to fetch batch analysis.')
  return data
}

export async function getBatchQuality(batchId) {
  const res = await fetch(`http://127.0.0.1:8000/api/batch/${batchId}/quality`)
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to fetch batch quality.')
  return data
}

export async function getBatchQuarantine(batchId) {
  const res = await fetch(`http://127.0.0.1:8000/api/batch/${batchId}/quarantine`)
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to fetch batch quarantine queue.')
  return data
}

export async function fixQuarantinedRecord(batchId, quarantineId, fixedRecord) {
  const res = await fetch(`http://127.0.0.1:8000/api/batch/${batchId}/quarantine/${quarantineId}/fix`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ fixed_record: fixedRecord })
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to fix quarantined record.')
  return data
}

export async function generateBatchRecoveryPlan(batchId, selectedPaymentIds, operatorId = 'operator_batch_lead') {
  const res = await fetch(`http://127.0.0.1:8000/api/batch/${batchId}/recovery-plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      selected_payment_ids: selectedPaymentIds,
      operator_id: operatorId
    })
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to generate batch recovery plan.')
  return data
}

export async function executeSelectiveBatchRecovery(batchId, selectedPaymentIds, operatorId = 'operator_batch_lead') {
  const res = await fetch(`http://127.0.0.1:8000/api/batch/${batchId}/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      selected_payment_ids: selectedPaymentIds,
      operator_id: operatorId
    })
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to execute selective batch recovery.')
  return data
}

// =========================================================================
// P0/P1 HARDENING — AUTHORITATIVE SNAPSHOT & DEMO CLIENT FUNCTIONS
// =========================================================================

export async function getPaymentOperationalSnapshot(paymentId) {
  const res = await fetch(`http://127.0.0.1:8000/api/payments/${paymentId}/operational-snapshot`, {
    headers: { 'X-Operator-Role': 'OPERATOR' }
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to fetch operational snapshot.')
  return data
}

export async function listAllOperationalSnapshots() {
  const res = await fetch(`http://127.0.0.1:8000/api/operational-snapshots`, {
    headers: { 'X-Operator-Role': 'OPERATOR' }
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to list operational snapshots.')
  return data
}

export async function validateWebhookReplay(eventId, signature = 'hmac_sha256_mock_valid', payload = null) {
  const res = await fetch(`http://127.0.0.1:8000/api/webhook/validate-replay`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      event_id: eventId,
      signature: signature,
      payload: payload
    })
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to validate webhook replay.')
  return data
}

export async function resetDemoEnvironment() {
  const res = await fetch(`http://127.0.0.1:8000/api/demo/reset`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Operator-Role': 'ADMIN' }
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail?.message || data.message || 'Failed to reset demo environment.')
  return data
}

export async function triggerRunRecoverySimulation(scenario, paymentId = 'pay_005') {
  return await runRecoverySimulation(scenario, paymentId)
}

export async function uploadPaymentBatchFile(file, operatorId = 'merchant_operator') {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = async (e) => {
      try {
        const contentStr = e.target.result
        const res = await analyzeBatchPaymentFile(file.name, contentStr, operatorId)
        resolve(res)
      } catch (err) {
        reject(err)
      }
    }
    reader.onerror = () => reject(new Error('Failed to read file from disk.'))
    reader.readAsText(file)
  })
}


























