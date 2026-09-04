// Computed from batch_recovery_log.json + telemetry_batch.json
// Total = sum of all amounts: 8400 + 2500 + 12000 + 5600 + 3100 = 31600
// Recovered = pay_004 only: 5600
// Recovery rate = 5600 / 31600 = 17.7215... %

export const metrics = {
  revenueAtRisk: 31600,
  revenueRecovered: 5600,
  recoveryRate: 17.72,
  paymentsMonitored: 5,
  autoRecoveryCount: 2,   // pay_001, pay_004
  humanReviewCount: 2,    // pay_002, pay_005
  stoppedCount: 1,        // pay_003
  successCount: 1,        // pay_004 (SUCCESS within AUTO RECOVERY)
  revenuePendingReview: 5600,   // pay_002 + pay_005
  revenueStopped: 12000,        // pay_003
  revenueHalted: 8400,          // pay_001 (STOPPED – order already existed)
}

export const revenueBreakdown = [
  { label: 'Recovered', value: 5600, color: '#00e5a0', textColor: '#00e5a0' },
  { label: 'Pending Review', value: 5600, color: '#f59e0b', textColor: '#f59e0b' },
  { label: 'Stopped / Halted', value: 20400, color: '#ef4444', textColor: '#ef4444' },
]
