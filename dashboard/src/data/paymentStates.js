/**
 * RecoverIQ — Authoritative Payment State Definitions (Topic 1.5.1)
 * Mirror of Python src/state_machine.py for frontend UI components.
 */

export const PAYMENT_STATES = {
  CREATED: {
    machine_value: 'CREATED',
    label: 'Created',
    description: 'Payment transaction initialized in payment gateway.',
    category: 'INITIAL',
    is_terminal: false,
    badge_color: 'slate'
  },
  PROCESSING: {
    machine_value: 'PROCESSING',
    label: 'Processing',
    description: 'Payment transaction is currently in-flight with gateway or banking rails.',
    category: 'IN_PROGRESS',
    is_terminal: false,
    badge_color: 'blue'
  },
  SUCCESS: {
    machine_value: 'SUCCESS',
    label: 'Success',
    description: 'Payment was successfully captured by the payment gateway.',
    category: 'TERMINAL_SUCCESS',
    is_terminal: true,
    badge_color: 'emerald'
  },
  FAILED: {
    machine_value: 'FAILED',
    label: 'Failed',
    description: 'Payment capture failed or customer transaction was rejected.',
    category: 'TERMINAL_FAILURE',
    is_terminal: true,
    badge_color: 'rose'
  },
  PENDING: {
    machine_value: 'PENDING',
    label: 'Pending',
    description: 'Payment state is awaiting asynchronous verification or webhook confirmation.',
    category: 'AWAITING_INPUT',
    is_terminal: false,
    badge_color: 'amber'
  },
  HUMAN_REVIEW: {
    machine_value: 'HUMAN_REVIEW',
    label: 'Human Review',
    description: 'Payment requires operator approval before recovery.',
    category: 'ACTION_REQUIRED',
    is_terminal: false,
    badge_color: 'amber'
  },
  RECOVERING: {
    machine_value: 'RECOVERING',
    label: 'Recovering',
    description: 'An approved recovery action is being executed.',
    category: 'IN_PROGRESS',
    is_terminal: false,
    badge_color: 'blue'
  },
  RECOVERED: {
    machine_value: 'RECOVERED',
    label: 'Recovered',
    description: 'Recovery completed and payment state was successfully verified.',
    category: 'TERMINAL_SUCCESS',
    is_terminal: true,
    badge_color: 'emerald'
  },
  RECOVERY_FAILED: {
    machine_value: 'RECOVERY_FAILED',
    label: 'Recovery Failed',
    description: 'Recovery action executed but post-recovery verification failed.',
    category: 'TERMINAL_FAILURE',
    is_terminal: true,
    badge_color: 'rose'
  },
  REFUNDED: {
    machine_value: 'REFUNDED',
    label: 'Refunded',
    description: 'Transaction amount was refunded to customer account.',
    category: 'TERMINAL_REFUND',
    is_terminal: true,
    badge_color: 'purple'
  },
  ESCALATED: {
    machine_value: 'ESCALATED',
    label: 'Escalated',
    description: 'Incident routed to Merchant Engineering on-call for technical investigation.',
    category: 'ACTION_REQUIRED',
    is_terminal: false,
    badge_color: 'indigo'
  },
  STOPPED: {
    machine_value: 'STOPPED',
    label: 'Stopped',
    description: 'Automated processing was intentionally stopped.',
    category: 'STOPPED',
    is_terminal: true,
    badge_color: 'slate'
  }
}

export const LEGACY_STATE_MAPPINGS = {
  'HUMAN REVIEW': 'HUMAN_REVIEW',
  'HUMAN_REVIEW': 'HUMAN_REVIEW',
  'PENDING_REVIEW': 'HUMAN_REVIEW',
  'MANUAL_REVIEW': 'HUMAN_REVIEW',
  'REVIEW': 'HUMAN_REVIEW',
  'AUTO RECOVERY': 'RECOVERING',
  'AUTO_RECOVERY': 'RECOVERING',
  'RECOVERING': 'RECOVERING',
  'RECOVERABLE': 'PENDING',
  'STOP': 'STOPPED',
  'STOPPED': 'STOPPED',
  'HALTED': 'STOPPED',
  'NO ACTION': 'SUCCESS',
  'NO_ACTION': 'SUCCESS',
  'HEALTHY': 'SUCCESS',
  'SUCCESS': 'SUCCESS',
  'SUCCESSFUL': 'SUCCESS',
  'RECOVERED': 'RECOVERED',
  'RESOLVED': 'RECOVERED',
  'FAILED': 'FAILED',
  'RECOVERY_FAILED': 'RECOVERY_FAILED',
  'PENDING': 'PENDING',
  'PROCESSING': 'PROCESSING',
  'QUEUED': 'PROCESSING',
  'REFUNDED': 'REFUNDED',
  'ESCALATED': 'ESCALATED'
}

export function normalizePaymentState(rawState) {
  if (!rawState) return 'PENDING'
  const cleaned = String(rawState).trim().toUpperCase()
  if (PAYMENT_STATES[cleaned]) return cleaned
  if (LEGACY_STATE_MAPPINGS[cleaned]) return LEGACY_STATE_MAPPINGS[cleaned]
  if (cleaned.includes('HUMAN') || cleaned.includes('REVIEW')) return 'HUMAN_REVIEW'
  if (cleaned.includes('RECOVERED') || cleaned.includes('RESOLVED')) return 'RECOVERED'
  if (cleaned.includes('RECOVER')) return 'RECOVERING'
  if (cleaned.includes('STOP') || cleaned.includes('HALT')) return 'STOPPED'
  if (cleaned.includes('REFUND')) return 'REFUNDED'
  if (cleaned.includes('ESCALAT')) return 'ESCALATED'
  if (cleaned.includes('FAIL')) return 'FAILED'
  if (cleaned.includes('SUCCESS') || cleaned.includes('HEALTHY')) return 'SUCCESS'
  return 'PENDING'
}

export const VALID_STATE_TRANSITIONS = {
  CREATED: ['PROCESSING'],
  PROCESSING: ['SUCCESS', 'FAILED', 'PENDING'],
  PENDING: ['SUCCESS', 'FAILED', 'HUMAN_REVIEW'],
  FAILED: ['HUMAN_REVIEW', 'STOPPED'],
  HUMAN_REVIEW: ['RECOVERING', 'ESCALATED', 'STOPPED'],
  RECOVERING: ['RECOVERED', 'RECOVERY_FAILED', 'ESCALATED'],
  RECOVERY_FAILED: ['HUMAN_REVIEW', 'ESCALATED', 'STOPPED'],
  ESCALATED: ['HUMAN_REVIEW', 'STOPPED'],
  SUCCESS: ['REFUNDED'],
  RECOVERED: ['REFUNDED'],
  REFUNDED: [],
  STOPPED: []
}

export function isValidTransition(currentState, nextState) {
  const curr = normalizePaymentState(currentState)
  const nxt = normalizePaymentState(nextState)
  const allowed = VALID_STATE_TRANSITIONS[curr] || []
  return allowed.includes(nxt)
}

export function getAllowedTransitions(currentState) {
  const curr = normalizePaymentState(currentState)
  return VALID_STATE_TRANSITIONS[curr] || []
}

