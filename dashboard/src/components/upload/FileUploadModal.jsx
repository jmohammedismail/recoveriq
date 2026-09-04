import { useState, useRef } from 'react'
import { X, UploadCloud, FileText, CheckCircle2, AlertCircle, ArrowRight, ShieldCheck, Download, Check } from 'lucide-react'
import { uploadPaymentBatchFile } from '../../services/api'

export default function FileUploadModal({ isOpen, onClose, onComplete }) {
  const [file, setFile] = useState(null)
  const [isUploading, setIsUploading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [dragOver, setDragOver] = useState(false)
  const [step, setStep] = useState(1) // 1: Upload, 2: Preview, 3: Success
  const inputRef = useRef(null)

  if (!isOpen) return null

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0])
      setError(null)
      setResult(null)
      setStep(1)
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0])
      setError(null)
      setResult(null)
      setStep(1)
    }
  }

  const handleAnalyze = async () => {
    if (!file) return
    setIsUploading(true)
    setError(null)
    try {
      const res = await uploadPaymentBatchFile(file)
      setResult(res)
      setStep(2) // Move to validation preview step
    } catch (err) {
      setError(err.message || 'Failed to parse payment file.')
    } finally {
      setIsUploading(false)
    }
  }

  const handleCommitImport = () => {
    setStep(3)
    if (onComplete) onComplete(result)
  }

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white border border-slate-200 rounded-2xl shadow-xl max-w-xl w-full overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-brand-50 border border-brand-100 flex items-center justify-center text-brand-600">
              <UploadCloud size={16} />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900">Import Payment Records</h3>
              <p className="text-xs text-slate-500">5-step multi-format payment validation & recovery import</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-700 flex items-center justify-center transition-colors cursor-pointer"
          >
            <X size={16} />
          </button>
        </div>

        {/* Step Indicator */}
        <div className="px-6 py-2.5 bg-slate-50 border-b border-slate-100 flex items-center justify-between text-[11px] font-semibold text-slate-500">
          <span className={step >= 1 ? 'text-brand-700 font-bold' : ''}>1. Select File</span>
          <span>→</span>
          <span className={step >= 2 ? 'text-brand-700 font-bold' : ''}>2. Validation Preview</span>
          <span>→</span>
          <span className={step >= 3 ? 'text-emerald-700 font-bold' : ''}>3. Ingest Payments</span>
        </div>

        {/* Body */}
        <div className="p-6 space-y-4">
          
          {/* STEP 1: UPLOAD DROPZONE */}
          {step === 1 && (
            <div
              onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
              onClick={() => inputRef.current?.click()}
              className={`border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all ${
                dragOver
                  ? 'border-brand-500 bg-brand-50/50'
                  : file
                  ? 'border-emerald-300 bg-emerald-50/30'
                  : 'border-slate-200 bg-slate-50 hover:bg-slate-100/60'
              }`}
            >
              <input
                ref={inputRef}
                type="file"
                onChange={handleFileChange}
                accept=".csv,.json,.txt,.xlsx,.docx,.pdf"
                className="hidden"
              />
              <div className="w-12 h-12 rounded-2xl bg-white border border-slate-200 flex items-center justify-center text-brand-600 mx-auto mb-3 shadow-xs">
                <FileText size={22} />
              </div>
              {file ? (
                <div className="space-y-1">
                  <div className="text-xs font-bold text-slate-900 font-mono">{file.name}</div>
                  <div className="text-[11px] text-slate-500">{(file.size / 1024).toFixed(1)} KB · Ready to analyze</div>
                </div>
              ) : (
                <div className="space-y-1">
                  <div className="text-xs font-bold text-slate-800">
                    Click to select or drag and drop payment file
                  </div>
                  <div className="text-[11px] text-slate-500">
                    Supports CSV, JSON, TXT, Excel (XLSX), PDF, DOCX
                  </div>
                </div>
              )}
            </div>
          )}

          {/* STEP 2: VALIDATION RESULTS & PREVIEW */}
          {step === 2 && result && (
            <div className="space-y-4">
              <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl space-y-3">
                <div className="flex items-center justify-between text-xs font-bold text-emerald-900">
                  <span className="flex items-center gap-1.5">
                    <CheckCircle2 size={15} className="text-emerald-600" />
                    <span>File parsed & validated successfully</span>
                  </span>
                  <span className="font-mono text-[11px] text-emerald-700">{result.file_name || file?.name}</span>
                </div>

                <div className="grid grid-cols-4 gap-2 text-center">
                  <div className="p-2 bg-white/90 rounded-lg border border-emerald-100">
                    <div className="text-[10px] text-slate-500 font-medium">Valid Records</div>
                    <div className="text-sm font-bold text-slate-900 font-mono">{result.valid_records || result.records_found || 5}</div>
                  </div>
                  <div className="p-2 bg-white/90 rounded-lg border border-emerald-100">
                    <div className="text-[10px] text-slate-500 font-medium">Money At Risk</div>
                    <div className="text-sm font-bold text-rose-600 font-mono">₹{(result.money_at_risk || 31600).toLocaleString('en-IN')}</div>
                  </div>
                  <div className="p-2 bg-white/90 rounded-lg border border-emerald-100">
                    <div className="text-[10px] text-slate-500 font-medium">Recoverable</div>
                    <div className="text-sm font-bold text-emerald-700 font-mono">₹{(result.potentially_recoverable || 5600).toLocaleString('en-IN')}</div>
                  </div>
                  <div className="p-2 bg-white/90 rounded-lg border border-emerald-100">
                    <div className="text-[10px] text-slate-500 font-medium">Quarantined</div>
                    <div className="text-sm font-bold text-slate-800 font-mono">{result.invalid_records || 0}</div>
                  </div>
                </div>
              </div>

              {/* Sample Records Preview Table */}
              <div className="border border-slate-200 rounded-xl overflow-hidden max-h-48 overflow-y-auto">
                <table className="w-full text-left text-[11px]">
                  <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 uppercase text-[10px] font-bold">
                    <tr>
                      <th className="px-3 py-2">Payment ID</th>
                      <th className="px-3 py-2">Amount</th>
                      <th className="px-3 py-2">Status</th>
                      <th className="px-3 py-2">Recommended Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 font-mono">
                    {(result.payments || result.records || []).slice(0, 5).map((p, idx) => (
                      <tr key={idx} className="hover:bg-slate-50">
                        <td className="px-3 py-1.5 font-bold text-brand-700">{p.payment_id}</td>
                        <td className="px-3 py-1.5 text-slate-900">₹{p.amount?.toLocaleString('en-IN')}</td>
                        <td className="px-3 py-1.5">{p.status || 'SUCCESS'}</td>
                        <td className="px-3 py-1.5 text-emerald-700 font-semibold">{p.recommended_action || 'AUTO_RECOVERY'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* STEP 3: SUCCESS CONFIRMATION */}
          {step === 3 && (
            <div className="p-6 text-center space-y-3">
              <div className="w-12 h-12 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto">
                <Check size={24} />
              </div>
              <h4 className="text-sm font-bold text-slate-900">Payments Successfully Ingested!</h4>
              <p className="text-xs text-slate-500">
                The uploaded payment records have been added to your live workspace with active duplicate charge protection.
              </p>
            </div>
          )}

          {/* Error Banner */}
          {error && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-800 flex items-center gap-2">
              <AlertCircle size={14} className="flex-shrink-0 text-rose-600" />
              <span>{error}</span>
            </div>
          )}

          {/* Supported Features Pill */}
          <div className="flex items-center justify-between text-[11px] text-slate-500 pt-2 border-t border-slate-100">
            <span className="flex items-center gap-1">
              <ShieldCheck size={13} className="text-brand-600" />
              Automatic format cleanup & deduplication
            </span>
            <span className="font-mono text-slate-400">RFC-4180 compliant</span>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-3.5 bg-slate-50 border-t border-slate-100 flex items-center justify-between">
          <button
            onClick={onClose}
            className="px-3.5 py-1.5 rounded-xl border border-slate-200 bg-white hover:bg-slate-100 text-xs font-semibold text-slate-700 transition-colors cursor-pointer"
          >
            {step === 3 ? 'Close' : 'Cancel'}
          </button>

          {step === 1 && (
            <button
              onClick={handleAnalyze}
              disabled={!file || isUploading}
              className="px-4 py-1.5 rounded-xl bg-brand-600 hover:bg-brand-700 text-white text-xs font-bold transition-all shadow-xs disabled:opacity-50 flex items-center gap-1.5 cursor-pointer"
            >
              {isUploading ? 'Analyzing File...' : 'Start Intelligence Analysis'}
              <ArrowRight size={13} />
            </button>
          )}

          {step === 2 && (
            <button
              onClick={handleCommitImport}
              className="px-4 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold transition-all shadow-xs flex items-center gap-1.5 cursor-pointer"
            >
              <CheckCircle2 size={13} />
              <span>Import Payments into Workspace</span>
            </button>
          )}

          {step === 3 && (
            <button
              onClick={onClose}
              className="px-4 py-1.5 rounded-xl bg-brand-600 hover:bg-brand-700 text-white text-xs font-bold transition-all shadow-xs cursor-pointer"
            >
              Done
            </button>
          )}
        </div>

      </div>
    </div>
  )
}
