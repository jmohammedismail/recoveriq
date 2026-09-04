import { useEffect, useState } from 'react'
import { Clock } from 'lucide-react'

export default function StatusBar() {
  const [time, setTime] = useState(new Date())

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  const formatted = time.toLocaleTimeString('en-IN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })

  return (
    <div className="h-7 bg-slate-100/80 border-b border-slate-200/70 flex items-center justify-between px-6 text-xs text-slate-500">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1 text-[11px] font-mono">
          <Clock size={11} className="text-slate-400" />
          <span>{formatted} IST</span>
        </div>
        <span className="text-slate-300">·</span>
        <span className="text-[11px]">Merchant: <strong className="text-slate-700 font-semibold">Acme Payments</strong></span>
      </div>

      <div className="flex items-center gap-2 text-[11px]">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
        <span className="text-slate-600 font-medium">Autonomous Recovery Pipeline Active</span>
      </div>
    </div>
  )
}
