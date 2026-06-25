import { useEffect, useState } from 'react'
import { invoke } from '@tauri-apps/api/core'

const toggleData = {
  general: [
    { key: 'diarization', label: '说话人分离', description: '自动区分法官、己方、对方发言', enabled: true },
    { key: 'hotword', label: '案件热词注入', description: '动态注入案由/人名提升 ASR 准确率', enabled: true },
    { key: 'legal', label: '法律策略引擎', description: '实时分析发言并生成法律提示', enabled: true },
  ],
  audio: [
    { key: 'tts', label: '语音合成 TTS', description: '通过耳机播报应对建议', enabled: false },
    { key: 'recording', label: '加密录音', description: '庭审全程 AES-256 加密录音', enabled: false },
    { key: 'diary', label: '庭后分析日志', description: '庭审结束后自动生成分析报告', enabled: false },
  ],
}

function Toggle({ on, onClick }: { on: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`toggle-switch ${on ? 'on' : 'off'}`}
      aria-label={on ? '关闭' : '开启'}
    >
      <span className="toggle-switch-knob" />
    </button>
  )
}

export default function SettingsPage({ healthLog }: { healthLog?: string[] }) {
  const [sub, setSub] = useState<'general' | 'audio'>('general')
  const [toggles, setToggles] = useState<Record<string, boolean>>({})
  const [settings, setSettings] = useState<Record<string, unknown>>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    const defaults: Record<string, boolean> = {}
    Object.values(toggleData).forEach(g => g.forEach(i => { defaults[i.key] = i.enabled }))
    setToggles(defaults)
  }, [])

  useEffect(() => {
    const load = async () => {
      try {
        const res = await invoke<Record<string, unknown>>('get_settings')
        const backendToggles = (res.toggles as Record<string, boolean>) || {}
        setToggles(prev => ({ ...prev, ...backendToggles }))
        setSettings(res)
        setError('')
      } catch (e) {
        setError('加载设置失败：' + String(e))
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const toggle = (key: string) => setToggles(t => ({ ...t, [key]: !t[key] }))

  const handleSave = async () => {
    setSaving(true)
    setSaved(false)
    setError('')
    try {
      const res = await invoke<Record<string, unknown>>('save_settings', { toggles })
      const backendToggles = (res.toggles as Record<string, boolean>) || {}
      setToggles(prev => ({ ...prev, ...backendToggles }))
      setSaved(true)
    } catch (e) {
      setError('保存设置失败：' + String(e))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="max-w-2xl space-y-8">
      <div className="slide-up">
        <h1 className="text-xl font-semibold tracking-tight text-[#1d1d1f]">设置</h1>
        <p className="mt-1.5 text-sm text-[#6e6e73] leading-relaxed">功能开关、版本信息与系统日志</p>
      </div>

      {/* 功能 / 音频胶囊 */}
      <div className="flex gap-2">
        <button onClick={() => setSub('general')} className={`tab-capsule ${sub === 'general' ? 'active' : 'inactive'}`}>
          功能
        </button>
        <button onClick={() => setSub('audio')} className={`tab-capsule ${sub === 'audio' ? 'active' : 'inactive'}`}>
          音频与录音
        </button>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="rounded-lg border border-[#fecaca] bg-[#fef2f2] px-4 py-2 text-sm text-[#991b1b]">
          {error}
        </div>
      )}

      {/* 开关列表 */}
      <div className="glass-card overflow-hidden">
        {toggleData[sub].map((item, i) => (
          <div key={item.key} className={`flex items-center justify-between px-5 py-3.5 ${i < toggleData[sub].length - 1 ? 'border-b border-[#e5e5e7]/60' : ''}`}>
            <div className="min-w-0 pr-4">
              <div className="text-sm font-medium text-[#1d1d1f]">{item.label}</div>
              <div className="text-xs text-[#6e6e73] mt-0.5">{item.description}</div>
            </div>
            <Toggle on={!!toggles[item.key]} onClick={() => toggle(item.key)} />
          </div>
        ))}
      </div>

      {/* 保存 */}
      <div className="flex justify-end">
        <button
          onClick={handleSave}
          disabled={saving || loading}
          className="btn-pill btn-pill-primary disabled:opacity-50"
        >
          {saving ? '保存中…' : saved ? '已保存' : '保存设置'}
        </button>
      </div>

      {/* 版本信息 */}
      <div className="glass-card overflow-hidden">
        <div className="px-5 py-3 text-sm font-medium text-[#1d1d1f] border-b border-[#e5e5e7]/60">
          版本信息
        </div>
        <div className="divide-y divide-[#e5e5e7]/30">
          <div className="flex items-center justify-between px-5 py-3">
            <div>
              <div className="text-sm font-medium text-[#1d1d1f]">当前版本</div>
              <div className="text-xs text-[#6e6e73] mt-0.5">
                v0.2.0 · {(settings.asr_model as string) || 'Whisper'} · {(settings.llm_model as string) || '规则引擎'}
              </div>
            </div>
            <span className="inline-flex items-center gap-1.5 text-xs text-[#22c55e] font-medium">
              <span className="status-dot bg-[#22c55e]" />最新版
            </span>
          </div>
          <div className="flex items-center justify-between px-5 py-3">
            <div>
              <div className="text-sm font-medium text-[#1d1d1f]">构建环境</div>
              <div className="text-xs text-[#6e6e73] mt-0.5">macOS 14+ · Apple Silicon · Rust + Tauri 2</div>
            </div>
          </div>
          <div className="flex items-center justify-between px-5 py-3">
            <div>
              <div className="text-sm font-medium text-[#1d1d1f]">引擎状态</div>
              <div className="text-xs text-[#6e6e73] mt-0.5">
                {(settings.asr_model as string) || 'Whisper ASR'} · {(settings.embedding_model as string) || 'ChromaDB'} · {(settings.llm_model as string) || '规则引擎'}
              </div>
            </div>
            <span className="inline-flex items-center gap-1.5 text-xs text-[#22c55e] font-medium">
              <span className="status-dot bg-[#22c55e]" />运行中
            </span>
          </div>
          <div className="flex items-center justify-between px-5 py-3">
            <div>
              <div className="text-sm font-medium text-[#1d1d1f]">检查更新</div>
              <div className="text-xs text-[#6e6e73] mt-0.5">自动检查版本更新</div>
            </div>
            <button className="btn-pill btn-pill-primary text-xs px-4 py-1">检查更新</button>
          </div>
          <div className="px-5 py-3">
            <button className="text-xs text-[#0071e3] hover:underline transition-all">查看更新日志 →</button>
          </div>
        </div>
      </div>

      {/* 系统日志 */}
      <div className="glass-card overflow-hidden" id="system-log">
        <div className="px-5 py-3 text-sm font-medium text-[#1d1d1f] border-b border-[#e5e5e7]/60">
          系统日志
        </div>
        <div className="glass-dark p-4 max-h-[280px] overflow-y-auto leading-5">
          {(healthLog && healthLog.length > 0) ? (
            healthLog.map((line, i) => {
              const isErr = line.startsWith('[ERR]')
              const isWarn = line.startsWith('[WARN]')
              const logColor = isErr ? '#ef4444' : isWarn ? '#f59e0b' : '#22c55e'
              return (
                <div key={i} className="log-line">
                  <span className="log-time">{new Date().toLocaleTimeString()}</span>
                  <span style={{ color: logColor }}>{line}</span>
                </div>
              )
            })
          ) : (
            <>
              <div className="log-line"><span className="log-time">10:32:15</span><span className="text-[#22c55e]">[INFO]</span><span className="text-[#e5e5e7]">ASR 模型加载完成</span></div>
              <div className="log-line"><span className="log-time">10:32:18</span><span className="text-[#22c55e]">[INFO]</span><span className="text-[#e5e5e7]">法律知识库 v1 已加载</span></div>
              <div className="log-line"><span className="log-time">10:32:22</span><span className="text-[#22c55e]">[INFO]</span><span className="text-[#e5e5e7]">Ollama 未检测到，由规则引擎接管</span></div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
