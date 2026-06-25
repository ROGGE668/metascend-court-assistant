export default function KnowledgePage() {
  const categories = ['全部', '民法典', '民事诉讼法', '司法解释', '指导案例', '借贷纠纷', '离婚纠纷', '劳动纠纷']
  const docs = [
    { name: '中华人民共和国民法典', category: '民法典', status: '已加载', chunks: 1260, date: '2026-06-20' },
    { name: '中华人民共和国民事诉讼法', category: '民事诉讼法', status: '已加载', chunks: 840, date: '2026-06-20' },
    { name: '最高人民法院关于审理民间借贷案件适用法律若干问题的规定', category: '司法解释', status: '已加载', chunks: 210, date: '2026-06-21' },
    { name: '最高人民法院关于适用〈中华人民共和国民法典〉婚姻家庭编的解释（一）', category: '司法解释', status: '已加载', chunks: 180, date: '2026-06-21' },
    { name: '指导案例64号·借贷合同纠纷', category: '指导案例', status: '已加载', chunks: 45, date: '2026-06-22' },
    { name: '劳动争议调解仲裁法', category: '劳动纠纷', status: '未加载', chunks: 0, date: '-' },
    { name: '民事证据规定', category: '司法解释', status: '索引中', chunks: 0, date: '-' },
  ]

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">本地向量知识库</h1>
          <p className="mt-1 text-sm text-[#6e6e73]">法律法条、司法解释与指导案例的本地向量索引，离线可用。</p>
        </div>
        <div className="flex gap-2">
          <button className="rounded-full border border-[#e5e5e7]/60 px-4 py-1.5 text-sm hover:bg-black/5 transition-all">📥 批量导入</button>
          <button className="rounded-full bg-[#0071e3] px-4 py-1.5 text-sm text-white hover:bg-[#005bbf] transition-all">+ 添加文档</button>
        </div>
      </div>

      <section className="rounded-lg border border-[#e5e5e7]/60 p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold">知识库概览</h2>
          <span className="text-xs text-[#6e6e73]">共 5 个文档已加载 · 向量维度 768 · 使用 ChromaDB</span>
        </div>
        <div className="grid grid-cols-4 gap-4">
          <div className="rounded-lg border border-[#e5e5e7] bg-[#f9fafb] p-4 text-center">
            <div className="text-2xl font-semibold text-[#0071e3]">5</div>
            <div className="mt-1 text-xs text-[#6e6e73]">已加载文档</div>
          </div>
          <div className="rounded-lg border border-[#e5e5e7] bg-[#f9fafb] p-4 text-center">
            <div className="text-2xl font-semibold text-[#0071e3]">2,535</div>
            <div className="mt-1 text-xs text-[#6e6e73]">向量分块</div>
          </div>
          <div className="rounded-lg border border-[#e5e5e7] bg-[#f9fafb] p-4 text-center">
            <div className="text-2xl font-semibold text-[#0071e3]">7</div>
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
              <button key={cat} className={`shrink-0 rounded-full px-3 py-1 text-xs ${cat === '全部' ? 'bg-[#0071e3] text-white' : 'bg-[#f5f5f7] text-[#6e6e73] hover:bg-[#e5e5e7]'}`}>
                {cat}
              </button>
            ))}
          </div>
          <div className="relative">
            <input placeholder="搜索法条..." className="w-48 rounded-lg border border-[#e5e5e7] px-3 py-1.5 text-xs focus:border-[#0071e3] focus:outline-none" />
          </div>
        </div>
        <div className="divide-y divide-[#f5f5f7]">
          {docs.map((doc, i) => (
            <div key={i} className="flex items-center gap-4 px-5 py-3 hover:bg-[#f5f5f7]">
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium">{doc.name}</div>
                <div className="mt-0.5 text-xs text-[#6e6e73]">
                  <span className="rounded bg-[#f5f5f7] px-1.5 py-0.5">{doc.category}</span>
                  {doc.chunks > 0 && <span className="ml-3">{doc.chunks} 个向量分块</span>}
                  {doc.date !== '-' && <span className="ml-3">导入于 {doc.date}</span>}
                </div>
              </div>
              <span className={`flex items-center gap-1.5 text-xs ${
                doc.status === '已加载' ? 'text-[#22c55e]' :
                doc.status === '索引中' ? 'text-[#f59e0b]' : 'text-[#6e6e73]'
              }`}>
                <span className={`h-1.5 w-1.5 rounded-full ${
                  doc.status === '已加载' ? 'bg-[#22c55e]' :
                  doc.status === '索引中' ? 'bg-[#f59e0b]' : 'bg-[#6e6e73]'
                }`} />
                {doc.status}
              </span>
              <button className="rounded-full border border-[#e5e5e7]/60 px-3 py-1 text-xs text-[#6e6e73] hover:bg-black/5 transition-all hover:bg-[#f5f5f7]">详情</button>
            </div>
          ))}
        </div>
      </section>

      <div className="flex items-center justify-between rounded-lg border border-[#e5e5e7] bg-white px-4 py-3 text-xs text-[#6e6e73]">
        <span>向量检索后端：ChromaDB · 嵌入模型：BAAI/bge-large-zh-v1.5</span>
        <span>存储路径：~/.cache/metascend/knowledge_base</span>
      </div>
    </div>
  )
}
