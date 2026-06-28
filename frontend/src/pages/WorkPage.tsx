import { useState, useEffect, useRef } from 'react'
import { invoke } from '@tauri-apps/api/core'
import { listen } from '@tauri-apps/api/event'

type ServiceStatus = Record<string, string>

// 启动宽限期：sidecar 启动需要几秒到十几秒，期间不显示红色错误。
const STARTUP_GRACE_MS = 15000

export default function WorkPage() {
  const pageStartTime = useRef(Date.now())
  const [running, setRunning] = useState(false)
  const [transcript, setTranscript] = useState('等待庭审发言…')
  const [legalHint, setLegalHint] = useState('等待对方发言中的法律要点…')
  const [countermeasure, setCountermeasure] = useState('暂无应对建议…')
  const [latency, setLatency] = useState('')
  const [serviceStatus, setServiceStatus] = useState<ServiceStatus>({})
  const [error, setError] = useState('')

  const [calibratingRole, setCalibratingRole] = useState<string | null>(null)
  const [calibratedRoles, setCalibratedRoles] = useState<Set<string>>(new Set())

  // 订阅流水线实时转写事件
  useEffect(() => {
    const unlisten = listen<Record<string, unknown>>('transcript:new', (event) => {
      const entry = event.payload
      const speaker = (entry.speaker as string) || '未知'
      const text = (entry.text as string) || ''
      const ts = (entry.timestamp as string) || ''
      if (text) {
        setTranscript(prev => {
          const line = `[${ts}] 【${speaker}】${text}`
          return prev === '等待庭审发言…' ? line : prev + '\n' + line
        })
      }
    })
    return () => { unlisten.then(fn => fn()) }
  }, [])

  // 轮询状态和建议（低频）
  useEffect(() => {
    const poll = async () => {
      try {
        const status = await invoke<Record<string, unknown>>('get_status')
        setServiceStatus((status.service_status as ServiceStatus) || {})
        setLatency(status.latency as string || '')
        setRunning(!!status.courtroom_running)
        setError('')
      } catch (e) {
        setError(String(e))
      }
      try {
        const s = await invoke<Record<string, unknown>>('get_suggestion')
        const text = (s.text as string) || ''
        const laws = (s.laws as string[]) || []
        if (text && text !== '等待庭审发言...') {
          setLegalHint(text)
          setCountermeasure(laws.length > 0 ? '参考：' + laws.join(' · ') : '暂无应对建议…')
        }
      } catch {
        // ignore
      }
    }
    poll()
    const id = setInterval(poll, 3000)
    return () => clearInterval(id)
  }, [])

  const toggle = async () => {
    const next = !running
    try {
      if (next) {
        await invoke('start_courtroom')
      } else {
        await invoke('stop_courtroom')
      }
      setRunning(next)
      setError('')
    } catch (e) {
      setError(String(e))
    }
  }

  const calibrate = async (role: string) => {
    setError('')
    setCalibratingRole(role)
    try {
      const res = await invoke<Record<string, unknown>>('calibrate_role', { role })
      if (res.ok) {
        setCalibratedRoles((prev) => new Set(prev).add(role))
      } else {
        setError(`声纹校准失败：${res.message || '请检查麦克风'}`)
      }
    } catch (e) {
      setError(String(e))
    } finally {
      setCalibratingRole(null)
    }
  }

  const statusLabel = (key: string) => {
    const raw = serviceStatus[key] || '未启用'
    return raw
  }

  const inGrace = Date.now() - pageStartTime.current < STARTUP_GRACE_MS

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">庭审实时辅助</h1>
          <p className="mt-1.5 text-sm text-[#6e6e73] leading-relaxed">实时语音识别、说话人分离、法律策略提示，全部在本地运行。</p>
        </div>
        <button
          onClick={toggle}
          className="rounded-full bg-[#0071e3] px-5 py-1.5 text-sm text-white hover:bg-[#005bbf] transition-all shrink-0"
        >
          {running ? '⏸ 暂停庭审' : '▶ 开始庭审'}
        </button>

      </div>

      {error && !inGrace && (
        <div className="rounded-lg border border-[#fecaca] bg-[#fef2f2] px-4 py-2 text-sm text-[#991b1b]">
          后端连接异常：{error}
        </div>
      )}
      {error && inGrace && (
        <div className="rounded-lg border border-[#fde68a] bg-[#fffbeb] px-4 py-2 text-sm text-[#92400e]">
          后端启动中，请稍候…
        </div>
      )}

      {/* 服务状态 */}
      <div className="flex gap-2">
        <ServiceCard title="语音识别 ASR" status={statusLabel('语音识别 ASR')} />
        <ServiceCard title="说话人分离" status={statusLabel('说话人分离')} />
        <ServiceCard title="法律策略引擎" status={statusLabel('法律策略引擎')} />
        <ServiceCard title="语音合成 TTS" status={statusLabel('语音合成 TTS')} />
      </div>

      {/* 声纹校准 */}
      <div className="rounded-lg border border-[#e5e5e7] p-3">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-xs font-medium shrink-0">🎤 声纹校准</span>
            <span className="text-xs text-[#6e6e73] hidden sm:inline">录制法官、己方、对方各 5 秒样本</span>
          </div>
          <span className="text-xs text-[#6e6e73] shrink-0">{latency || '延迟就绪'}</span>
        </div>
        <div className="flex gap-2 mt-2">
          <CalibrationCard
            role="法官"
            isRecording={calibratingRole === '法官'}
            isCalibrated={calibratedRoles.has('法官')}
            onRecord={() => calibrate('法官')}
          />
          <CalibrationCard
            role="己方"
            isRecording={calibratingRole === '己方'}
            isCalibrated={calibratedRoles.has('己方')}
            onRecord={() => calibrate('己方')}
          />
          <CalibrationCard
            role="对方"
            isRecording={calibratingRole === '对方'}
            isCalibrated={calibratedRoles.has('对方')}
            onRecord={() => calibrate('对方')}
          />
        </div>
      </div>

      {/* 实时转写 */}
      <div className="rounded-lg border border-[#e5e5e7] bg-white p-4">
        <h3 className="text-sm font-semibold text-[#1d1d1f]">实时转写</h3>
        <p className="mt-2 text-sm text-[#1d1d1f] whitespace-pre-wrap min-h-[3rem]">{transcript}</p>
      </div>

      {/* 法律提示 + 应对建议 */}
      <div className="grid grid-cols-2 gap-4">
        <div className="rounded-lg border border-[#bfdbfe] bg-[#eff6ff] p-4">
          <h3 className="text-sm font-semibold text-[#1e3a8a]">💡 法律提示</h3>
          <p className="mt-2 text-sm text-[#1e3a8a]">{legalHint}</p>
        </div>
        <div className="rounded-lg border border-[#bbf7d0] bg-[#f0fdf4] p-4">
          <h3 className="text-sm font-semibold text-[#166534]">🛡️ 应对建议</h3>
          <p className="mt-2 text-sm text-[#166534]">{countermeasure}</p>
        </div>
      </div>

      <p className="text-xs text-[#6e6e73]">本系统输出仅供参考，不构成法律意见。用户对庭上陈述与决策负有最终责任。</p>
    </div>
  )
}

function ServiceCard({ title, status }: { title: string; status: string }) {
  const color = status === '运行中' || status === '就绪' || status === '已加载' || status === '已启用' ? '#22c55e' : status === '异常' ? '#ef4444' : '#f59e0b'
  return (
    <div className="flex flex-1 items-center gap-2 rounded-lg border border-[#e5e5e7] px-3 py-2">
      <span className="h-2 w-2 rounded-full shrink-0" style={{ backgroundColor: color }} />
      <div className="min-w-0 leading-tight">
        <div className="text-xs text-[#6e6e73]">{title}</div>
        <div className="text-xs font-medium">{status}</div>
      </div>
    </div>
  )
}

function CalibrationCard({
  role,
  isRecording,
  isCalibrated,
  onRecord,
}: {
  role: string
  isRecording: boolean
  isCalibrated: boolean
  onRecord: () => void
}) {
  const status = isRecording ? '录制中…' : isCalibrated ? '已录制' : '未录制'
  return (
    <div className="flex flex-1 items-center gap-2 rounded-lg border border-[#e5e5e7] px-2.5 py-1.5">
      <span className="text-xs">🎙️</span>
      <div className="min-w-0 leading-tight">
        <div className="text-xs font-medium">{role}</div>
        <div className="text-xs text-[#6e6e73]">{status}</div>
      </div>
      <button
        onClick={onRecord}
        disabled={isRecording}
        className={`ml-auto rounded-full border border-[#e5e5e7] px-3 py-1 text-xs transition-all ${
          isRecording ? 'opacity-60 cursor-not-allowed' : 'hover:bg-black/5'
        }`}
      >
        {isRecording ? '录制中…' : isCalibrated ? '重新录制' : '录制'}
      </button>
    </div>
  )
}
