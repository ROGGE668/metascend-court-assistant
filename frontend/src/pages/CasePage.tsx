import { useState, useEffect } from 'react'
import { invoke } from '@tauri-apps/api/core'
import { open } from '@tauri-apps/plugin-dialog'

type CaseItem = {
  case_id: string
  title: string
  case_type: string
  updated_at: string
}

type EvidenceItem = {
  name: string
  suffix: string
  size: number
  modified_at: string
}

const typeMap: Record<string, string> = {
  loan: '民间借贷',
  divorce: '离婚纠纷',
  labor: '劳动争议',
  contract: '合同纠纷',
  other: '其他',
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

export default function CasePage() {
  const [cases, setCases] = useState<CaseItem[]>([])
  const [selectedCase, setSelectedCase] = useState<CaseItem | null>(null)
  const [evidence, setEvidence] = useState<EvidenceItem[]>([])
  const [error, setError] = useState('')

  const loadCases = async () => {
    try {
      const list = await invoke<CaseItem[]>('list_cases')
      setCases(list)
      if (list.length > 0 && !selectedCase) {
        setSelectedCase(list[0])
      }
      setError('')
    } catch (e) {
      setError('加载案件失败：' + String(e))
    }
  }

  const loadEvidence = async () => {
    try {
      const list = await invoke<EvidenceItem[]>('list_evidence')
      setEvidence(list)
    } catch (e) {
      setError('加载证据失败：' + String(e))
    }
  }

  useEffect(() => {
    loadCases()
    loadEvidence()
  }, [])

  const handleCreateCase = async () => {
    const title = window.prompt('请输入案件标题')
    if (!title) return
    try {
      await invoke('create_case', { title, case_type: 'other' })
      await loadCases()
    } catch (e) {
      setError('新建案件失败：' + String(e))
    }
  }

  const handleImportEvidence = async () => {
    try {
      const path = await open({ multiple: false, directory: false })
      if (!path) return
      await invoke('import_evidence', { sourcePath: path })
      await loadEvidence()
    } catch (e) {
      setError('导入证据失败：' + String(e))
    }
  }

  const handleDeleteEvidence = async (name: string) => {
    if (!window.confirm('确定删除证据 ' + name + ' 吗？')) return
    try {
      await invoke('delete_evidence', { name })
      await loadEvidence()
    } catch (e) {
      setError('删除证据失败：' + String(e))
    }
  }

  const caseEvidence = selectedCase
    ? evidence.filter(e => e.name.toLowerCase().includes(selectedCase.case_id.toLowerCase()))
    : evidence

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">案件档案管理</h1>
          <p className="mt-1 text-sm text-[#6e6e73]">统一管理案件、当事人信息与证据文件，全部保存在本地。</p>
        </div>
        <div className="flex gap-2 shrink-0">
          <button
            onClick={handleImportEvidence}
            className="rounded-full border border-[#e5e5e7] px-4 py-1.5 text-sm hover:bg-black/5 transition-all hover:border-[#0071e3] hover:text-[#0071e3]"
          >
            + 导入证据
          </button>
          <button
            onClick={handleCreateCase}
            className="rounded-full bg-[#0071e3] px-4 py-1.5 text-sm text-white hover:bg-[#005bbf] transition-all"
          >
            + 新建案件
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-[#fecaca] bg-[#fef2f2] px-4 py-2 text-sm text-[#991b1b]">
          {error}
        </div>
      )}

      <div className="grid grid-cols-5 gap-5">
        {/* 案件列表 — 左 2 列 */}
        <section className="col-span-2 rounded-lg border border-[#e5e5e7]">
          <div className="border-b border-[#e5e5e7] px-4 py-3 text-sm font-medium">案件列表</div>
          <div className="divide-y divide-[#f5f5f7]">
            {cases.map(c => (
              <button
                key={c.case_id}
                onClick={() => setSelectedCase(c)}
                className={`w-full px-4 py-3 text-left hover:bg-[#f5f5f7] ${selectedCase?.case_id === c.case_id ? 'bg-[#e8f4fd]' : ''}`}
              >
                <div className="text-sm font-medium">{c.title}</div>
                <div className="mt-0.5 text-xs text-[#6e6e73]">{typeMap[c.case_type] || c.case_type}</div>
                <div className="mt-0.5 text-xs text-[#6e6e73]">{c.case_id}</div>
              </button>
            ))}
            {cases.length === 0 && (
              <div className="p-4 text-sm text-[#6e6e73]">暂无案件</div>
            )}
          </div>
        </section>

        {/* 选中案件的详情 + 证据 — 右 3 列 */}
        <section className="col-span-3 space-y-4">
          {selectedCase && (
            <>
              {/* 案件详情 */}
              <div className="rounded-lg border border-[#e5e5e7] p-4">
                <h2 className="text-sm font-semibold mb-3">案件详情</h2>
                <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
                  <div><span className="text-[#6e6e73]">案号：</span>{selectedCase.case_id}</div>
                  <div><span className="text-[#6e6e73]">案由：</span>{typeMap[selectedCase.case_type] || selectedCase.case_type}</div>
                  <div className="col-span-2"><span className="text-[#6e6e73]">更新于：</span>{selectedCase.updated_at}</div>
                </div>
              </div>

              {/* 证据文件 */}
              <div className="rounded-lg border border-[#e5e5e7]">
                <div className="flex items-center justify-between border-b border-[#e5e5e7] px-4 py-3">
                  <h2 className="text-sm font-semibold">证据文件</h2>
                  <button
                    onClick={handleImportEvidence}
                    className="text-xs text-[#0071e3] hover:underline"
                  >
                    + 添加证据
                  </button>
                </div>
                {caseEvidence.length > 0 ? (
                  <div className="divide-y divide-[#f5f5f7]">
                    {caseEvidence.map(e => (
                      <div key={e.name} className="flex items-center gap-4 px-4 py-3 hover:bg-[#f5f5f7]">
                        <span className="text-base">📄</span>
                        <div className="min-w-0 flex-1">
                          <div className="text-sm">{e.name}</div>
                          <div className="text-xs text-[#6e6e73]">{e.suffix.toUpperCase()} · {formatBytes(e.size)} · {e.modified_at.slice(0, 10)}</div>
                        </div>
                        <button className="rounded-full border border-[#e5e5e7] px-3 py-1 text-xs text-[#6e6e73] hover:bg-black/5 transition-all hover:bg-[#f5f5f7]">查看</button>
                        <button
                          onClick={() => handleDeleteEvidence(e.name)}
                          className="rounded-full border border-[#e5e5e7] px-3 py-1 text-xs text-[#ef4444] hover:bg-red-50 transition-all hover:bg-[#fef2f2]"
                        >
                          删除
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="p-6 text-sm text-[#6e6e73]">暂无证据文件</div>
                )}
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  )
}
