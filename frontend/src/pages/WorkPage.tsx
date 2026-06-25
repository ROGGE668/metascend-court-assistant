import { useState } from 'react'

type WorkStatus = { asr: string; diarization: string; legal: string; tts: string }
const initialStatus: WorkStatus = { asr: '初始化中', diarization: '未启用', legal: '未启用', tts: '未启用' }

export default function WorkPage() {
  const [status] = useState<WorkStatus>(initialStatus)
  const [running, setRunning] = useState(false)
  const [transcript] = useState('等待庭审发言…')
  const [legalHint] = useState('等待对方发言中的法律要点…')
  const [countermeasure] = useState('暂无应对建议…')
  const [latency] = useState('')

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">庭审实时辅助</h1>
          <p className="mt-1.5 text-sm text-[#6e6e73] leading-relaxed">实时语音识别、说话人分离、法律策略提示，全部在本地运行。</p>
        </div>
        <button
          onClick={() => setRunning(r => !r)}
          className="rounded-full bg-[#0071e3] px-5 py-1.5 text-sm text-white hover:bg-[#005bbf] transition-all shrink-0"
        >
          {running ? '⏸ 暂停庭审' : '▶ 开始庭审'}
        </button>
      </div>

      {/* 服务状态 */}
      <div className="flex gap-2">
        <ServiceCard title="语音识别 ASR" status={status.asr} />
        <ServiceCard title="说话人分离" status={status.diarization} />
        <ServiceCard title="法律策略引擎" status={status.legal} />
        <ServiceCard title="语音合成 TTS" status={status.tts} />
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
          <CalibrationCard role="法官" />
          <CalibrationCard role="己方" />
          <CalibrationCard role="对方" />
        </div>
      </div>

      {/* 实时转写 */}
      <div className="rounded-lg border border-[#e5e5e7] p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold">实时转写</h2>
          <span className="text-xs text-[#6e6e73]">{running ? '正在监听' : '已暂停'}</span>
        </div>
        <div className="min-h-[160px] max-h-[300px] overflow-auto rounded-lg bg-[#f9fafb] p-4 text-sm text-[#1d1d1f]">
          {transcript}
        </div>
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
  const color = status === '运行中' || status === '就绪' || status === '已加载' ? '#22c55e' : status === '异常' ? '#ef4444' : '#f59e0b'
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

function CalibrationCard({ role }: { role: string }) {
  return (
    <div className="flex flex-1 items-center gap-2 rounded-lg border border-[#e5e5e7] px-2.5 py-1.5">
      <span className="text-xs">🎙️</span>
      <div className="min-w-0 leading-tight">
        <div className="text-xs font-medium">{role}</div>
        <div className="text-xs text-[#6e6e73]">未录制</div>
      </div>
      <button className="ml-auto rounded-full border border-[#e5e5e7] px-3 py-1 text-xs hover:bg-black/5 transition-all">
        录制
      </button>
    </div>
  )
}
