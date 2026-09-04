import { useState } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, LabelList,
} from 'recharts'
import { ChevronDown, ChevronUp, DollarSign } from 'lucide-react'
import { metrics as defaultMetrics } from '../../data/metrics'

const CustomTooltip = ({ active, payload, totalAtRisk }) => {
  if (active && payload && payload.length) {
    const d = payload[0]
    return (
      <div className="bg-white border border-slate-200 rounded-lg px-2.5 py-1.5 text-xs shadow-md">
        <div className="font-semibold text-slate-900">{d.payload.name}</div>
        <div style={{ color: d.payload.color }} className="font-bold">
          ₹{d.value.toLocaleString('en-IN')}
        </div>
        <div className="text-slate-500 text-[10px]">
          {totalAtRisk > 0 ? ((d.value / totalAtRisk) * 100).toFixed(1) : 0}% of total at-risk
        </div>
      </div>
    )
  }
  return null
}

export default function RevenueChart({ dynamicMetrics }) {
  const [isOpen, setIsOpen] = useState(true)
  const m = dynamicMetrics || defaultMetrics

  const recoveredVal = m.revenueRecovered || 5600
  const pendingVal = m.revenuePendingReview !== undefined ? m.revenuePendingReview : 5600
  const stoppedVal = m.revenueStopped !== undefined ? m.revenueStopped : (m.revenueAtRisk - recoveredVal - pendingVal)

  const chartData = [
    { name: 'Recovered', value: recoveredVal, color: '#10b981' },
    { name: 'Pending Review', value: pendingVal, color: '#f59e0b' },
    { name: 'Stopped / Halted', value: stoppedVal > 0 ? stoppedVal : 20400, color: '#ef4444' },
  ]

  return (
    <div className="bg-white border border-slate-200 rounded-2xl shadow-xs p-4 overflow-hidden space-y-3">
      {/* Header with Toggle */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <DollarSign size={14} className="text-brand-600" />
          <span className="text-xs font-bold text-slate-800 uppercase tracking-wider">Revenue Breakdown</span>
        </div>
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="text-xs text-slate-500 hover:text-slate-700 flex items-center gap-1"
        >
          <span className="text-[11px]">{isOpen ? 'Minimize' : 'Expand'}</span>
          {isOpen ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
        </button>
      </div>

      {/* Chart Body */}
      {isOpen && (
        <div className="pt-1 space-y-2">
          <ResponsiveContainer width="100%" height={120}>
            <BarChart
              data={chartData}
              layout="vertical"
              margin={{ top: 0, right: 65, bottom: 0, left: 0 }}
              barSize={16}
            >
              <XAxis type="number" hide />
              <YAxis
                type="category"
                dataKey="name"
                width={105}
                tick={{ fill: '#475569', fontSize: 11, fontWeight: 500 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip content={<CustomTooltip totalAtRisk={m.revenueAtRisk || 31600} />} cursor={{ fill: 'rgba(241,245,249,0.7)' }} />
              <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                {chartData.map((entry) => (
                  <Cell key={entry.name} fill={entry.color} />
                ))}
                <LabelList
                  dataKey="value"
                  position="right"
                  formatter={(v) => `₹${Number(v).toLocaleString('en-IN')}`}
                  style={{ fill: '#334155', fontSize: 11, fontWeight: 600 }}
                />
              </Bar>
            </BarChart>
          </ResponsiveContainer>

          {/* Compact Legend */}
          <div className="pt-2 border-t border-slate-100 flex items-center justify-between flex-wrap gap-2 text-[11px]">
            {chartData.map((d) => (
              <div key={d.name} className="flex items-center gap-1">
                <div className="w-2 h-2 rounded-xs" style={{ backgroundColor: d.color }} />
                <span className="text-slate-600 font-medium">{d.name}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
