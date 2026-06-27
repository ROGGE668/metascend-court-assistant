import { useState, useEffect, useRef } from 'react'
import { invoke } from '@tauri-apps/api/core'
import WorkPage from './pages/WorkPage'
import ChatPage from './pages/ChatPage'
import CasePage from './pages/CasePage'
import KnowledgePage from './pages/KnowledgePage'
import SettingsPage from './pages/SettingsPage'

type Page = 'work' | 'chat' | 'case' | 'knowledge' | 'settings'
type ServiceHealth = 'normal' | 'abnormal' | 'checking' | 'starting'

// 启动宽限期：后端 sidecar 启动可能需要数秒，期间显示“启动中”而不是“异常”。
const STARTUP_GRACE_MS = 15000

export default function App() {
  const [page, setPage] = useState<Page>('work')
  const [health, setHealth] = useState<ServiceHealth>('starting')
  const [healthLog, setHealthLog] = useState<string[]>([])
  const appStartTime = useRef(Date.now())

  useEffect(() => {
    document.title = 'Metascend 庭审助手'
  }, [])

  // 每 5 秒自检
  useEffect(() => {
    const check = async () => {
      const checks: string[] = []
      let allOk = true
      try {
        const hasTauri = typeof window !== 'undefined' && (window as any).__TAURI__ && (window as any).__TAURI__.core
        if (hasTauri) {
          checks.push('[OK] Tauri IPC 可用')
          try {
            const status = await invoke<string>('local_backend_status')
            if (status.startsWith('error:')) {
              allOk = false
              checks.push('[ERR] 后端状态: ' + status)
            } else {
              checks.push('[OK] 后端状态: ' + status)
            }
          } catch (e) {
            allOk = false
            checks.push('[ERR] 后端未响应：' + String(e))
          }
        } else {
          checks.push('[WARN] 非 Tauri 环境（浏览器开发模式）')
        }
        checks.push('[OK] 前端渲染正常')
      } catch (e) {
        allOk = false
        checks.push('[ERR] ' + String(e))
      }
      setHealthLog(checks)

      const inGrace = Date.now() - appStartTime.current < STARTUP_GRACE_MS
      if (allOk) {
        setHealth('normal')
      } else if (inGrace) {
        setHealth('starting')
      } else {
        setHealth('abnormal')
      }
    }
    check()
    const interval = setInterval(check, 5000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="flex h-screen w-screen flex-col bg-[#f5f5f7] text-[#1d1d1f]">
      <header className="flex h-[32px] shrink-0 items-center justify-end border-b border-[#e5e5e7] bg-white px-4 select-none">
        <StatusBadge health={health} setPage={setPage} />
      </header>
      <div className="flex flex-1 overflow-hidden">
        <aside className="flex w-[264px] shrink-0 flex-col border-r border-[#e5e5e7] bg-white">
          <nav className="flex-1 overflow-y-auto p-4">
            <div className="mb-3 flex rounded-full bg-[#f5f5f7] p-0.5">
              <ModeTab label="Work" active={page !== 'chat'} onClick={() => setPage('work')} />
              <ModeTab label="Chat" active={page === 'chat'} onClick={() => setPage('chat')} />
            </div>
            <div className="mb-6 space-y-1">
              <NavItem label="庭审实时辅助" page="work" current={page} onClick={setPage} />
              <NavItem label="案件档案管理" page="case" current={page} onClick={setPage} />
              <NavItem label="本地向量知识库" page="knowledge" current={page} onClick={setPage} />
            </div>
          </nav>
          <UserArea page={page} setPage={setPage} />
        </aside>
        <main className="flex-1 overflow-y-auto bg-[#f5f5f7] p-8">
          {page === 'work' && <WorkPage />}
          {page === 'case' && <CasePage />}
          {page === 'knowledge' && <KnowledgePage />}
          {page === 'chat' && <ChatPage />}
          {page === 'settings' && <SettingsPage healthLog={healthLog} />}
        </main>
      </div>
    </div>
  )
}

function ModeTab({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`flex-1 rounded-full py-1.5 text-xs font-medium transition-all ${
        active ? 'bg-white text-[#1d1d1f] shadow-sm' : 'text-[#6e6e73]'
      }`}
    >
      {label}
    </button>
  )
}

function NavItem({ label, page, current, onClick }: { label: string; page: Page; current: Page; onClick: (p: Page) => void }) {
  const active = current === page
  return (
    <button
      onClick={() => onClick(page)}
      className={`nav-item ${active ? 'active' : ''}`}
    >
      <span>{label}</span>
    </button>
  )
}

function UserArea({ page, setPage }: { page: Page; setPage: (p: Page) => void }) {
  return (
    <div className="border-t border-[#e5e5e7] px-4 py-3">
      <button
        onClick={() => setPage('settings')}
        className={`flex w-full items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-black/5 transition-all ${
          page === 'settings' ? 'nav-item active' : ''
        }`}
      >
        <div className="min-w-0">
          <div className="text-sm font-medium">设置</div>
        </div>
      </button>
    </div>
  )
}

function StatusBadge({ health, setPage }: { health: ServiceHealth; setPage: (p: Page) => void }) {
  const isNormal = health === 'normal'
  const isStarting = health === 'starting' || health === 'checking'
  const color = isStarting ? '#f59e0b' : isNormal ? '#22c55e' : '#ef4444'
  const label = isStarting ? '启动中…' : isNormal ? '服务正常' : '服务异常'
  return (
    <button
      onClick={() => { if (!isNormal && !isStarting) setPage('settings') }}
      className="inline-flex items-center gap-2 rounded-full border border-[#e5e5e7] bg-[#f5f5f7] px-3 py-1 text-xs text-[#6e6e73] hover:bg-black/5 transition-all"
      title={isStarting ? '后端正在启动…' : isNormal ? '系统自检正常' : '点击查看系统日志'}
    >
      <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color, boxShadow: `0 0 0 2px ${isNormal ? 'rgba(34,197,94,0.2)' : isStarting ? 'rgba(245,158,11,0.2)' : 'rgba(239,68,68,0.2)'}` }} />
      <span>{label}</span>
    </button>
  )
}
