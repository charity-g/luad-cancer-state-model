import { NavLink, Outlet, useMatch } from 'react-router-dom'

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `px-1 py-2 text-sm font-medium transition-colors border-b-2 ${
    isActive
      ? 'border-white text-white'
      : 'border-transparent text-white/60 hover:text-white hover:border-white/40'
  }`

export default function Layout() {
  const isModel = useMatch('/model')

  return (
    <div className="app-bg flex h-screen flex-col text-slate-900">
      <header className="flex-shrink-0 border-b border-white/20 bg-white/10 backdrop-blur-sm">
        <div className="flex items-center justify-between px-5 py-3">
          <span className="text-sm font-semibold tracking-tight text-white">
            Cancer State Model
          </span>
          <nav className="flex gap-1">
            <NavLink to="/" end className={linkClass}>
              Home
            </NavLink>
            <NavLink to="/model" className={linkClass}>
              Workspace
            </NavLink>
            <NavLink to="/acknowledgements" className={linkClass}>
              Acknowledgements
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
        <main className="flex flex-1 min-h-0 overflow-auto">
          <Outlet />
        </main>
      )}
    </div>
  )
}
