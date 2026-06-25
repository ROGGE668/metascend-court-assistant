import { useState } from 'react'

type Case = {
  id: number
  number: string
  name: string
  parties: string
  type: string
  date: string
}

const mockCases: Case[] = [
  { id: 1, number: '(2026) 京01民初123号', name: '张三诉李四民间借贷纠纷', parties: '原告: 张三 / 被告: 李四', type: '民间借贷', date: '2026-06-15' },
  { id: 2, number: '(2026) 沪02民终456号', name: '王五离婚财产分割上诉案', parties: '上诉人: 王五 / 被上诉人: 赵六', type: '离婚纠纷', date: '2026-06-18' },
  { id: 3, number: '(2026) 粤03民初789号', name: '某科技公司劳动争议案', parties: '原告: 某科技公司 / 被告: 员工刘某', type: '劳动争议', date: '2026-06-20' },
]

type Evidence = {
  id: number
  caseId: number
  name: string
  type: string
  date: string
  size: string
}

const mockEvidence: Evidence[] = [
  { id: 1, caseId: 1, name: '借条扫描件.pdf', type: '书证', date: '2026-06-10', size: '2.3 MB' },
  { id: 2, caseId: 1, name: '银行转账记录.xlsx', type: '书证', date: '2026-06-11', size: '156 KB' },
  { id: 3, caseId: 1, name: '微信聊天记录截屏.png', type: '电子数据', date: '2026-06-12', size: '4.1 MB' },
  { id: 4, caseId: 2, name: '结婚证复印件.jpg', type: '书证', date: '2026-06-16', size: '892 KB' },
  { id: 5, caseId: 2, name: '房产证复印件.pdf', type: '书证', date: '2026-06-16', size: '1.5 MB' },
  { id: 6, caseId: 3, name: '劳动合同.pdf', type: '书证', date: '2026-06-19', size: '3.2 MB' },
  { id: 7, caseId: 3, name: '考勤记录.xlsx', type: '电子数据', date: '2026-06-19', size: '234 KB' },
]

export default function CasePage() {
  const [selectedCase, setSelectedCase] = useState<Case | null>(mockCases[0])

  const caseEvidence = mockEvidence.filter(e => e.caseId === selectedCase?.id)

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">案件档案管理</h1>
          <p className="mt-1 text-sm text-[#6e6e73]">统一管理案件、当事人信息与证据文件，全部保存在本地。</p>
        </div>
        <div className="flex gap-2 shrink-0">
          <button className="rounded-full border border-[#e5e5e7] px-4 py-1.5 text-sm hover:bg-black/5 transition-all hover:border-[#0071e3] hover:text-[#0071e3]">+ 导入证据</button>
          <button className="rounded-full bg-[#0071e3] px-4 py-1.5 text-sm text-white hover:bg-[#005bbf] transition-all">+ 新建案件</button>
        </div>
      </div>

      <div className="grid grid-cols-5 gap-5">
        {/* 案件列表 — 左 2 列 */}
        <section className="col-span-2 rounded-lg border border-[#e5e5e7]">
          <div className="border-b border-[#e5e5e7] px-4 py-3 text-sm font-medium">案件列表</div>
          <div className="divide-y divide-[#f5f5f7]">
            {mockCases.map(c => (
              <button
                key={c.id}
                onClick={() => setSelectedCase(c)}
                className={`w-full px-4 py-3 text-left hover:bg-[#f5f5f7] ${selectedCase?.id === c.id ? 'bg-[#e8f4fd]' : ''}`}
              >
                <div className="text-sm font-medium">{c.name}</div>
                <div className="mt-0.5 text-xs text-[#6e6e73]">{c.number}</div>
                <div className="mt-0.5 text-xs text-[#6e6e73]">{c.parties}</div>
              </button>
            ))}
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
                  <div><span className="text-[#6e6e73]">案号：</span>{selectedCase.number}</div>
                  <div><span className="text-[#6e6e73]">案由：</span>{selectedCase.type}</div>
                  <div className="col-span-2"><span className="text-[#6e6e73]">当事人：</span>{selectedCase.parties}</div>
                  <div className="col-span-2"><span className="text-[#6e6e73]">立案日期：</span>{selectedCase.date}</div>
                </div>
              </div>

              {/* 证据文件 */}
              <div className="rounded-lg border border-[#e5e5e7]">
                <div className="flex items-center justify-between border-b border-[#e5e5e7] px-4 py-3">
                  <h2 className="text-sm font-semibold">证据文件</h2>
                  <button className="text-xs text-[#0071e3] hover:underline">+ 添加证据</button>
                </div>
                {caseEvidence.length > 0 ? (
                  <div className="divide-y divide-[#f5f5f7]">
                    {caseEvidence.map(e => (
                      <div key={e.id} className="flex items-center gap-4 px-4 py-3 hover:bg-[#f5f5f7]">
                        <span className="text-base">📄</span>
                        <div className="min-w-0 flex-1">
                          <div className="text-sm">{e.name}</div>
                          <div className="text-xs text-[#6e6e73]">{e.type} · {e.size} · {e.date}</div>
                        </div>
                        <button className="rounded-full border border-[#e5e5e7] px-3 py-1 text-xs text-[#6e6e73] hover:bg-black/5 transition-all hover:bg-[#f5f5f7]">查看</button>
                        <button className="rounded-full border border-[#e5e5e7] px-3 py-1 text-xs text-[#ef4444] hover:bg-red-50 transition-all hover:bg-[#fef2f2]">删除</button>
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
