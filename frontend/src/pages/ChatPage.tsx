export default function ChatPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">庭后分析</h1>
        <p className="mt-1 text-sm text-[#6e6e73]">基于本地知识库做问答、历史会话和策略报告。</p>
      </div>
      <section className="grid grid-cols-3 gap-4">
        <div className="col-span-2 rounded-lg border border-[#e5e5e7]/60 p-5">
          <h2 className="text-sm font-semibold">智能问答</h2>
          <div className="mt-3 h-72 overflow-auto rounded-lg bg-[#f9fafb] p-3 text-sm text-[#1d1d1f]">
            <p>你好，我是 Metascend 庭审助手。庭审结束后，你可以基于本地知识库问我任何法律分析问题。</p>
          </div>
          <div className="mt-3 flex gap-2">
            <input className="flex-1 rounded-lg border border-[#e5e5e7] px-3 py-2 text-sm" placeholder="输入问题..." />
            <button className="rounded-full bg-[#0071e3] px-5 py-2 text-sm text-white hover:bg-[#005bbf] transition-all">发送</button>
          </div>
        </div>
        <div className="space-y-4">
          <div className="rounded-lg border border-[#e5e5e7]/60 p-4">
            <h3 className="text-sm font-semibold">历史会话</h3>
            <p className="mt-2 text-sm text-[#6e6e73]">暂无历史会话。</p>
          </div>
          <div className="rounded-lg border border-[#e5e5e7]/60 p-4">
            <h3 className="text-sm font-semibold">策略报告</h3>
            <p className="mt-2 text-sm text-[#6e6e73]">庭审结束后可生成策略报告。</p>
          </div>
        </div>
      </section>
    </div>
  )
}
