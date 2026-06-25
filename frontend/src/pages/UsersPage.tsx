import { useState } from 'react'

type User = {
  id: number
  name: string
  role: string
  avatar: string
  status: '在线' | '离线' | '庭审中'
  lastActive: string
}

const initialUsers: User[] = [
  { id: 1, name: '法律助手', role: '系统账户', avatar: '法', status: '在线', lastActive: '刚刚' },
  { id: 2, name: '张三', role: '当事人', avatar: '张', status: '离线', lastActive: '昨天 15:23' },
  { id: 3, name: '李四', role: '律师', avatar: '李', status: '离线', lastActive: '3天前' },
]

export default function UsersPage() {
  const [users] = useState<User[]>(initialUsers)
  const [showNew, setShowNew] = useState(false)
  const [newName, setNewName] = useState('')
  const [newRole, setNewRole] = useState('当事人')

  const handleCreate = () => {
    if (!newName.trim()) return
    setShowNew(false)
    setNewName('')
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">用户管理</h1>
          <p className="mt-1.5 text-sm text-[#6e6e73] leading-relaxed">本地多账号切换与管理，数据仅保存在本机。</p>
        </div>
        <button
          onClick={() => setShowNew(true)}
          className="rounded-full bg-[#0071e3] px-4 py-1.5 text-sm text-white hover:bg-[#005bbf] transition-all"
        >
          + 新建用户
        </button>
      </div>

      <section className="rounded-lg border border-[#e5e5e7]">
        <div className="border-b border-[#e5e5e7] px-5 py-3 text-sm font-medium">用户列表</div>
        <div className="divide-y divide-[#f5f5f7]">
          {users.map(user => (
            <div key={user.id} className="flex items-center gap-4 px-5 py-4 hover:bg-[#f5f5f7]">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-[#667eea] to-[#764ba2] text-xs font-semibold text-white">
                {user.avatar}
              </span>
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium">{user.name}</div>
                <div className="text-xs text-[#6e6e73]">{user.role}</div>
              </div>
              <div className="flex items-center gap-3 text-xs">
                <span className={`flex items-center gap-1.5 ${user.status === '在线' ? 'text-[#22c55e]' : user.status === '庭审中' ? 'text-[#f59e0b]' : 'text-[#6e6e73]'}`}>
                  <span className={`h-1.5 w-1.5 rounded-full ${user.status === '在线' ? 'bg-[#22c55e]' : user.status === '庭审中' ? 'bg-[#f59e0b]' : 'bg-[#6e6e73]'}`} />
                  {user.status}
                </span>
                <span className="text-[#6e6e73]">{user.lastActive}</span>
                <button className="rounded-full border border-[#e5e5e7] px-3 py-1 text-xs text-[#6e6e73] hover:bg-black/5 transition-all hover:bg-[#f5f5f7]">切换</button>
                <button className="rounded-full border border-[#e5e5e7] px-3 py-1 text-xs text-[#ef4444] hover:bg-red-50 transition-all hover:bg-[#fef2f2]">删除</button>
              </div>
            </div>
          ))}
        </div>
      </section>

      {showNew && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
          <div className="w-96 rounded-xl bg-white p-6 shadow-2xl">
            <h3 className="text-base font-semibold mb-4">新建用户</h3>
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-[#6e6e73] mb-1">姓名</label>
                <input
                  value={newName}
                  onChange={e => setNewName(e.target.value)}
                  placeholder="输入姓名"
                  className="w-full rounded-lg border border-[#e5e5e7] px-3 py-2 text-sm focus:border-[#0071e3] focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-xs text-[#6e6e73] mb-1">角色</label>
                <select
                  value={newRole}
                  onChange={e => setNewRole(e.target.value)}
                  className="w-full rounded-lg border border-[#e5e5e7] px-3 py-2 text-sm focus:border-[#0071e3] focus:outline-none"
                >
                  <option>当事人</option>
                  <option>律师</option>
                  <option>法官</option>
                  <option>证人</option>
                  <option>旁听</option>
                </select>
              </div>
            </div>
            <div className="mt-6 flex justify-end gap-3">
              <button onClick={() => setShowNew(false)} className="rounded-full border border-[#e5e5e7] px-4 py-1.5 text-sm hover:bg-black/5 transition-all">取消</button>
              <button onClick={handleCreate} className="rounded-full bg-[#0071e3] px-4 py-1.5 text-sm text-white hover:bg-[#005bbf] transition-all">创建</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
