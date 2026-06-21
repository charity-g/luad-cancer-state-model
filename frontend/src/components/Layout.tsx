import { NavLink, Outlet, useMatch } from 'react-router-dom'

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `px-3 py-2 rounded-md text-sm font-medium transition-colors ${
    isActive ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
  }`

export default function Layout() {
  const isModel = useMatch('/model')

  return (
    <div className="flex h-screen flex-col bg-slate-50 text-slate-900">
      <header className="flex-shrink-0 border-b border-slate-200 bg-white">
        <div className="flex items-center justify-between px-5 py-3">
          <span className="text-sm font-semibold tracking-tight text-slate-800">
            Cancer State Model
          </span>
          <nav className="flex gap-1">
            <NavLink to="/" end className={linkClass}>
              Home
            </NavLink>
            <NavLink to="/model" className={linkClass}>
              Workspace
            </NavLink>
          </nav>
        </div>
      </header>

      {isModel ? (
        <div className="flex flex-1 min-h-0 overflow-hidden">
          <div className="flex flex-1 flex-col min-h-0 overflow-hidden w-full">
            <Outlet />
          </div>
        </div>
      ) : (
        <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8">
          <Outlet />
        </main>
      )}
    </div>
  )
}
