import { useState } from 'react'
import { RefreshCw } from 'lucide-react'
import clsx from 'clsx'
import { api } from '../lib/api'

interface ScanButtonProps {
  onComplete?: () => void
}

export default function ScanButton({ onComplete }: ScanButtonProps) {
  const [scanning, setScanning] = useState(false)
  const [lastResult, setLastResult] = useState<string | null>(null)

  const handleScan = async () => {
    setScanning(true)
    setLastResult(null)
    try {
      await api.triggerScan()
      // Poll for completion
      let tries = 0
      const poll = setInterval(async () => {
        tries++
        const status = await api.getScanStatus()
        if (!status.is_running || tries > 30) {
          clearInterval(poll)
          setScanning(false)
          if (status.last_result.events_scanned !== undefined) {
            setLastResult(
              `${status.last_result.events_scanned} Events, ${status.last_result.value_bets_found} Value Bets, ${status.last_result.arbitrage_found} Arbs`
            )
          }
          onComplete?.()
        }
      }, 1000)
    } catch {
      setScanning(false)
      setLastResult('Fehler beim Scan')
    }
  }

  return (
    <div className="flex items-center gap-3">
      <button
        onClick={handleScan}
        disabled={scanning}
        className={clsx(
          'btn-primary flex items-center gap-2',
          scanning && 'opacity-70 cursor-not-allowed'
        )}
      >
        <RefreshCw size={14} className={scanning ? 'animate-spin' : ''} />
        {scanning ? 'Scanne...' : 'Scan starten'}
      </button>
      {lastResult && (
        <span className="text-xs text-slate-400 font-mono">{lastResult}</span>
      )}
    </div>
  )
}
