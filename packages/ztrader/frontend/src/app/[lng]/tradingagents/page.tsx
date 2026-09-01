'use client'

import { useState } from 'react'

interface AnalysisResult {
  symbol: string
  signal: string
  confidence: number
  reasoning: string
  analysis_date: string
  risk_score: number
  agents_used: string[]
  supporting_data: Record<string, unknown>
}

export default function TradingAgentsPage() {
  const [symbol, setSymbol] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [error, setError] = useState('')

  const analyze = async () => {
    if (!symbol.trim()) return
    setLoading(true)
    setError('')
    setResult(null)

    try {
      const res = await fetch('/api/v1/tradingagents/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol: symbol.trim().toUpperCase() }),
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Analysis failed')
      }
      const data: AnalysisResult = await res.json()
      setResult(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Analysis failed')
    } finally {
      setLoading(false)
    }
  }

  const signalColor = (signal: string) => {
    switch (signal) {
      case 'buy': return 'text-green-400'
      case 'sell': return 'text-red-400'
      default: return 'text-yellow-400'
    }
  }

  return (
    <div className="min-h-screen bg-gray-900 text-white p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold mb-2">TradingAgents Analysis</h1>
        <p className="text-gray-400 mb-8">
          Multi-agent LLM-powered trading analysis
        </p>

        <div className="flex gap-4 mb-8">
          <input
            type="text"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && analyze()}
            placeholder="Enter symbol (e.g., NVDA, BTC-USD, XAUUSD)"
            className="flex-1 px-4 py-2 rounded bg-gray-800 border border-gray-700 text-white placeholder-gray-500"
            disabled={loading}
          />
          <button
            onClick={analyze}
            disabled={loading || !symbol.trim()}
            className="px-6 py-2 bg-blue-600 rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Analyzing...' : 'Analyze'}
          </button>
        </div>

        {error && (
          <div className="p-4 mb-6 bg-red-900/50 border border-red-700 rounded text-red-300">
            {error}
          </div>
        )}

        {result && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="p-4 bg-gray-800 rounded">
                <div className="text-sm text-gray-400">Signal</div>
                <div className={`text-2xl font-bold ${signalColor(result.signal)}`}>
                  {result.signal.toUpperCase()}
                </div>
              </div>
              <div className="p-4 bg-gray-800 rounded">
                <div className="text-sm text-gray-400">Confidence</div>
                <div className="text-2xl font-bold">
                  {(result.confidence * 100).toFixed(0)}%
                </div>
              </div>
              <div className="p-4 bg-gray-800 rounded">
                <div className="text-sm text-gray-400">Risk Score</div>
                <div className="text-2xl font-bold">
                  {(result.risk_score * 100).toFixed(0)}%
                </div>
              </div>
              <div className="p-4 bg-gray-800 rounded">
                <div className="text-sm text-gray-400">Date</div>
                <div className="text-lg font-bold">{result.analysis_date}</div>
              </div>
            </div>

            <div className="p-4 bg-gray-800 rounded">
              <h2 className="text-lg font-semibold mb-2">Reasoning</h2>
              <p className="text-gray-300 whitespace-pre-wrap">{result.reasoning}</p>
            </div>

            {result.agents_used.length > 0 && (
              <div className="p-4 bg-gray-800 rounded">
                <h2 className="text-lg font-semibold mb-2">Agents Used</h2>
                <div className="flex flex-wrap gap-2">
                  {result.agents_used.map((agent) => (
                    <span key={agent} className="px-3 py-1 bg-blue-900/50 text-blue-300 rounded-full text-sm">
                      {agent}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}