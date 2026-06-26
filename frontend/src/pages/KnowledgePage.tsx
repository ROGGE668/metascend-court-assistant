import { useState, useEffect } from 'react'
import { invoke } from '@tauri-apps/api/core'
import { open } from '@tauri-apps/plugin-dialog'

type Document = {
  id: string
  name: string
  category: string
  status: string
  chunks: number
  date: string
  path?: string
}

type DocContent = {
  type: 'text' | 'media'
  format: string
  content?: string
  path?: string
  note?: string
}

const categories = ['全部', '民法典', '民事诉讼法', '司法解释', '指导案例', '借贷纠纷', '离婚纠纷', '劳动纠纷', '其他']

export default function KnowledgePage() {
  const [docs, setDocs] = useState<Document[]>([])
  const [filtered, setFiltered] = useState<Document[]>([])
  const [category, setCategory] = useState('全部')
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [importing, setImporting] = useState(false)
  const [error, setError] = useState('')
  const [detail, setDetail] = useState<{ doc: Document; content: DocContent } | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      const res = await invoke<Record<string, unknown>>('list_documents')
      const list = (res.documents as Document[]) || []
      setDocs(list)
      setFiltered(list)
      setError('')
    } catch (e) {
      setError('加载知识库失败：' + String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  useEffect(() => {
    let list = docs
    if (category !== '全部') {
      list = list.filter(d => d.category === category)
    }
    if (query.trim()) {
      const q = query.toLowerCase()
      list = list.filter(d => d.name.toLowerCase().includes(q))
    }
    setFiltered(list)
  }, [category, query, docs])

  const handleSearch = async () => {
    if (!query.trim()) return
    setLoading(true)
    try {
      const res = await invoke<Record<string, unknown>>('search_documents', {
        query: query.trim(),
        category: category === '全部' ? null : category,
      })
      const results = (res.results as Array<{ law?: string; content?: string; case_type?: string }>) || []
      setFiltered(
        results.map((r, i) => ({
          id: 'search_' + i,
          name: r.law || (r.content ? r.content.slice(0, 30) : '搜索结果'),
          category: r.case_type || '搜索',
          status: '匹配',
          chunks: 1,
          date: '-',
        }))
      )
      setError('')
    } catch (e) {
      setError('搜索失败：' + String(e))
    } finally {
      setLoading(false)
    }
  }

  const handleImport = async () => {
    try {
      const sourcePath = await open({ multiple: false, directory: false })
      if (!sourcePath || Array.isArray(sourcePath)) return

      const defaultCategory = category !== '全部' ? category : '其他'
      const chosen = window.prompt(
        `请选择分类（默认：${defaultCategory}）\n支持 .json / .yaml / .pdf / 图片`,
        defaultCategory
      )
      if (!chosen) return

      setImporting(true)
      setError('')
      await invoke('import_knowledge_document', {
        sourcePath,
        category: chosen.trim() || defaultCategory,
      })
      await load()
    } catch (e) {
      setError('导入失败：' + String(e))
    } finally {
      setImporting(false)
    }
  }

  const handleDetail = async (doc: Document) => {
    if (!doc.path) {
      setDetail({
        doc,
        content: { type: 'text', format: 'builtin', content: '这是内置示例文档，没有本地源文件。' },
      })
      return
    }
    setLoading(true)
    try {
      const content = await invoke<DocContent>('get_knowledge_document', { path: doc.path })
      setDetail({ doc, content })
      setError('')
    } catch (e) {
      setError('读取详情失败：' + String(e))
    } finally {
      setLoading(false)
    }
  }

  const totalChunks = docs.reduce((sum, d) => sum + d.chunks, 0)

  const catButtonClass = (cat: string) => {
    const base = 'shrink-0 rounded-full px-3 py-1 text-xs '
    return cat === category
      ? base + 'bg-[#0071e3] text-white'
      : base + 'bg-[#f5f5f7] text-[#6e6e73] hover:bg-[#e5e5e7]'
  }

  const statusClass = (status: string) => {
    if (status === '已加载') return 'text-[#22c55e]'
    if (status === '索引中') return 'text-[#f59e0b]'
    return 'text-[#6e6e73]'
  }

  const dotClass = (status: string) => {
    if (status === '已加载') return 'bg-[#22c55e]'
    if (status === '索引中') return 'bg-[#f59e0b]'
    return 'bg-[#6e6e73]'
  }

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">本地向量知识库</h1>
          <p className="mt-1 text-sm text-[#6e6e73]">法律法条、司法解释与指导案例的本地向量索引，离线可用。</p>
        </div>
        <button
          onClick={handleImport}
          disabled={importing}
          className="rounded-full bg-[#0071e3] px-4 py-1.5 text-sm text-white hover:bg-[#005bbf] transition-all disabled:opacity-50"
        >
          {importing ? '导入中…' : '+ 导入文档'}
        </button>
      </div>

      {error && (
        <div className="rounded-lg border border-[#fecaca] bg-[#fef2f2] px-4 py-2 text-sm text-[#991b1b]">
          {error}
        </div>
      )}

      <section className="rounded-lg border border-[#e5e5e7]/60 p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold">知识库概览</h2>
          <span className="text-xs text-[#6e6e73]">共 {docs.length} 个文档已加载 · 向量维度 768 · 使用 ChromaDB</span>
        </div>
        <div className="grid grid-cols-4 gap-4">
          <div className="rounded-lg border border-[#e5e5e7] bg-[#f9fafb] p-4 text-center">
            <div className="text-2xl font-semibold text-[#0071e3]">{docs.length}</div>
            <div className="mt-1 text-xs text-[#6e6e73]">已加载文档</div>
          </div>
          <div className="rounded-lg border border-[#e5e5e7] bg-[#f9fafb] p-4 text-center">
            <div className="text-2xl font-semibold text-[#0071e3]">{totalChunks}</div>
            <div className="mt-1 text-xs text-[#6e6e73]">向量分块</div>
          </div>
          <div className="rounded-lg border border-[#e5e5e7] bg-[#f9fafb] p-4 text-center">
            <div className="text-2xl font-semibold text-[#0071e3]">{categories.length - 1}</div>
            <div className="mt-1 text-xs text-[#6e6e73]">法条分类</div>
          </div>
          <div className="rounded-lg border border-[#e5e5e7] bg-[#f9fafb] p-4 text-center">
            <div className="text-2xl font-semibold text-[#22c55e]">在线</div>
            <div className="mt-1 text-xs text-[#6e6e73]">引擎状态</div>
          </div>
        </div>
      </section>

      <section className="rounded-lg border border-[#e5e5e7]/60">
        <div className="flex items-center justify-between border-b border-[#e5e5e7] px-5 py-3">
          <div className="flex gap-2 overflow-x-auto">
            {categories.map(cat => (
              <button
                key={cat}
                onClick={() => setCategory(cat)}
                className={catButtonClass(cat)}
              >
                {cat}
              </button>
            ))}
          </div>
          <div className="relative flex gap-2">
            <input
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSearch()}
              placeholder="搜索法条..."
              className="w-48 rounded-lg border border-[#e5e5e7] px-3 py-1.5 text-xs focus:border-[#0071e3] focus:outline-none"
            />
            <button
              onClick={handleSearch}
              disabled={loading}
              className="rounded-full bg-[#0071e3] px-3 py-1.5 text-xs text-white hover:bg-[#005bbf] transition-all disabled:opacity-50"
            >
              {loading ? '…' : '搜索'}
            </button>
          </div>
        </div>
        <div className="divide-y divide-[#f5f5f7]">
          {filtered.map((doc, i) => (
            <div key={doc.id || String(i)} className="flex items-center gap-4 px-5 py-3 hover:bg-[#f5f5f7]">
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium">{doc.name}</div>
                <div className="mt-0.5 text-xs text-[#6e6e73]">
                  <span className="rounded bg-[#f5f5f7] px-1.5 py-0.5">{doc.category}</span>
                  {doc.chunks > 0 && <span className="ml-3">{doc.chunks} 个向量分块</span>}
                  {doc.date !== '-' && <span className="ml-3">导入于 {doc.date}</span>}
                </div>
              </div>
              <span className={'flex items-center gap-1.5 text-xs ' + statusClass(doc.status)}>
                <span className={'h-1.5 w-1.5 rounded-full ' + dotClass(doc.status)} />
                {doc.status}
              </span>
              <button
                onClick={() => handleDetail(doc)}
                className="rounded-full border border-[#e5e5e7]/60 px-3 py-1 text-xs text-[#6e6e73] hover:bg-black/5 transition-all hover:bg-[#f5f5f7]"
              >
                详情
              </button>
            </div>
          ))}
          {filtered.length === 0 && !loading && (
            <div className="p-6 text-sm text-[#6e6e73]">暂无文档</div>
          )}
        </div>
      </section>

      <div className="flex items-center justify-between rounded-lg border border-[#e5e5e7] bg-white px-4 py-3 text-xs text-[#6e6e73]">
        <span>向量检索后端：ChromaDB · 嵌入模型：BAAI/bge-large-zh-v1.5</span>
        <span>存储路径：~/.cache/metascend/knowledge_base</span>
      </div>

      {detail && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="max-h-[80vh] w-full max-w-2xl overflow-auto rounded-2xl border border-[#e5e5e7] bg-white p-6 shadow-xl">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h3 className="text-base font-semibold">{detail.doc.name}</h3>
                <p className="mt-1 text-xs text-[#6e6e73]">
                  分类：{detail.doc.category} · 状态：{detail.doc.status}
                </p>
              </div>
              <button
                onClick={() => setDetail(null)}
                className="rounded-full border border-[#e5e5e7] px-3 py-1 text-xs hover:bg-black/5"
              >
                关闭
              </button>
            </div>
            <div className="mt-4 rounded-lg border border-[#e5e5e7] bg-[#f9fafb] p-4">
              {detail.content.type === 'text' ? (
                <pre className="whitespace-pre-wrap text-sm text-[#1d1d1f] font-mono">
                  {detail.content.content}
                </pre>
              ) : (
                <div className="text-sm text-[#6e6e73]">
                  <p>文件格式：{detail.content.format}</p>
                  <p className="mt-1 break-all">路径：{detail.content.path}</p>
                  <p className="mt-2 text-[#f59e0b]">{detail.content.note}</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
