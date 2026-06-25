export default function EvidencePage() {
  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">证据管理</h1>
          <p className="mt-1.5 text-sm text-[#6e6e73] leading-relaxed">统一管理案件证据文件，全部保存在本地。</p>
        </div>
        <button className="rounded-full bg-[#0071e3] px-5 py-1.5 text-sm text-white hover:bg-[#005bbf] transition-all">+ 导入证据</button>
      </div>
      <section className="rounded-xl border border-[#e5e5e7] bg-white shadow-sm p-5">
        <div className="mb-3 text-sm font-medium">证据文件</div>
        <div className="rounded-lg bg-[#f9fafb] p-6 text-sm text-[#6e6e73]">暂无证据文件</div>
      </section>
    </div>
  )
}
