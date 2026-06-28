import { useState, useEffect, useRef } from 'react'
import { invoke } from '@tauri-apps/api/core'

type Message = {
  sender: string
  text: string
  ref: string
  time: string
}

type StrategyReport = {
  summary: string
  case_type: string
  key_points: string[]
  suggestions: string[]
  relevant_laws: string[]
  risk_analysis: string
  generated_at: string
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [reportLoading, setReportLoading] = useState(false)
  const [error, setError] = useState('')
  const [report, setReport] = useState<StrategyReport | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  const loadMessages = async () => {
    try {
      const list = await invoke<Message[]>('chat_messages')
      setMessages(list)
      setError('')
    } catch (e) {
      setError('加载会话失败：' + String(e))
    }
  }

  useEffect(() => {
    loadMessages()
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async () => {
    const text = input.trim()
    if (!text || loading) return
    setLoading(true)
    setError('')
    try {
      await invoke('chat_ask', { message: text })
      setInput('')
      await loadMessages()
    } catch (e) {
      setError('发送失败：' + String(e))
    } finally {
      setLoading(false)
    }
  }

  const handleGenerateReport = async () => {
    setReportLoading(true)
    setError('')
    try {
      const res = await invoke<{ ok: boolean; report?: StrategyReport; message?: string }>('generate_strategy_report')
      if (res.ok && res.report) {
        setReport(res.report)
      } else {
        setError(res.message || '生成报告失败')
      }
    } catch (e) {
      setError('生成报告失败：' + String(e))
    } finally {
      setReportLoading(false)
    }
  }

  const lastAI = messages.filter(m => m.sender === 'AI').pop()

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">庭后分析</h1>
        <p className="mt-1 text-sm text-[#6e6e73]">基于本地知识库做问答、历史会话和策略报告。</p>
      </div>

      {error && (
        <div className="rounded-lg border border-[#fecaca] bg-[#fef2f2] px-4 py-2 text-sm text-[#991b1b]">
          {error}
        </div>
      )}

      <section className="grid grid-cols-3 gap-4">
        <div className="col-span-2 rounded-lg border border-[#e5e5e7]/60 p-5">
          <h2 className="text-sm font-semibold">智能问答</h2>
          <div className="mt-3 h-72 overflow-auto rounded-lg bg-[#f9fafb] p-3 text-sm text-[#1d1d1f] space-y-3">
            {messages.length === 0 ? (
              <p>你好，我是 Metascend 庭审助手。庭审结束后，你可以基于本地知识库问我任何法律分析问题。</p>
            ) : (
              messages.map((m, i) => (
                <div key={i} className={`max-w-[85%] ${m.sender === 'User' ? 'ml-auto' : ''}`}>
                  <div
                    className={`rounded-2xl px-3.5 py-2.5 text-sm ${
                      m.sender === 'User'
                        ? 'bg-[#0071e3] text-white'
                        : 'bg-white border border-[#e5e5e7]'
                    }`}
                  >
                    {m.text}
                  </div>
                  {m.ref && (
                    <div className="mt-1 text-xs text-[#6e6e73]">{m.ref}</div>
                  )}
                </div>
              ))
            )}
            <div ref={bottomRef} />
          </div>
          <div className="mt-3 flex gap-2">
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSend()}
              disabled={loading}
              className="flex-1 rounded-lg border border-[#e5e5e7] px-3 py-2 text-sm focus:border-[#0071e3] focus:outline-none disabled:bg-[#f5f5f7]"
              placeholder="输入问题..."
            />
            <button
              onClick={handleSend}
              disabled={loading || !input.trim()}
              className="rounded-full bg-[#0071e3] px-5 py-2 text-sm text-white hover:bg-[#005bbf] transition-all disabled:opacity-50"
            >
              {loading ? '思考中…' : '发送'}
            </button>
          </div>
        </div>
        <div className="space-y-4">
          <div className="rounded-lg border border-[#e5e5e7]/60 p-4">
            <h3 className="text-sm font-semibold">历史会话</h3>
            {messages.length === 0 ? (
              <p className="mt-2 text-sm text-[#6e6e73]">暂无历史会话。</p>
            ) : (
              <div className="mt-2 max-h-48 overflow-auto space-y-1.5 text-sm">
                {messages.map((m, i) => (
                  <div key={i} className="truncate text-[#6e6e73]">
                    <span className="font-medium text-[#1d1d1f]">{m.sender === 'User' ? '你' : 'AI'}：</span>
                    {m.text}
                  </div>
                ))}
              </div>
            )}
          </div>
          <div className="rounded-lg border border-[#e5e5e7]/60 p-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold">策略报告</h3>
              <button
                onClick={handleGenerateReport}
                disabled={reportLoading}
                className="rounded-full bg-[#34c759] px-3 py-1 text-xs text-white hover:bg-[#2aa148] transition-all disabled:opacity-50"
              >
                {reportLoading ? '生成中…' : '生成报告'}
              </button>
            </div>
            {report ? (
              <div className="mt-2 text-sm space-y-2">
                <div className="rounded bg-[#f5f5f7] p-2">
                  <div className="font-medium text-xs text-[#6e6e73] mb-1">案件类型</div>
                  <div>{report.case_type}</div>
                </div>
                {report.key_points.length > 0 && (
                  <div>
                    <div className="font-medium text-xs text-[#6e6e73] mb-1">关键点</div>
                    <ul className="list-disc list-inside space-y-0.5">
                      {report.key_points.slice(0, 5).map((p, i) => (
                        <li key={i} className="text-xs">{p}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {report.suggestions.length > 0 && (
                  <div>
                    <div className="font-medium text-xs text-[#6e6e73] mb-1">建议</div>
                    <ul className="list-disc list-inside space-y-0.5">
                      {report.suggestions.slice(0, 3).map((s, i) => (
                        <li key={i} className="text-xs">{s}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {report.relevant_laws.length > 0 && (
                  <div>
                    <div className="font-medium text-xs text-[#6e6e73] mb-1">相关法律</div>
                    <div className="text-xs text-[#0071e3]">{report.relevant_laws.join(' · ')}</div>
                  </div>
                )}
                <div className="rounded bg-[#fef2f2] p-2">
                  <div className="font-medium text-xs text-[#991b1b] mb-1">风险分析</div>
                  <div className="text-xs">{report.risk_analysis}</div>
                </div>
                <div className="text-xs text-[#6e6e73]">生成时间：{report.generated_at}</div>
              </div>
            ) : lastAI ? (
              <div className="mt-2 text-sm space-y-1">
                <p>{lastAI.text}</p>
                {lastAI.ref && <p className="text-xs text-[#6e6e73]">{lastAI.ref}</p>}
              </div>
            ) : (
              <p className="mt-2 text-sm text-[#6e6e73]">庭审结束后可生成策略报告。</p>
            )}
          </div>
        </div>
      </section>

      <p className="text-xs text-[#6e6e73]">本系统输出仅供参考，不构成法律意见。用户对庭上陈述与决策负有最终责任。</p>
    </div>
  )
}
