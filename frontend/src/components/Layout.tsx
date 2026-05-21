import { ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { LogOut, Settings, BookOpen, LayoutDashboard, Home, PlusCircle } from 'lucide-react'

interface Props {
  children: ReactNode
  title?: string
}

export default function Layout({ children, title }: Props) {
  const { user, logout, isParent } = useAuthStore()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/parent/login')
  }

  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-white border-b border-gray-100 sticky top-0 z-40">
        <div className="max-w-5xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-2xl">🎓</span>
            <span className="font-bold text-primary-500 text-lg">MathTutor</span>
            {title && (
              <>
                <span className="text-gray-300 hidden sm:block">/</span>
                <span className="text-gray-600 font-medium hidden sm:block">{title}</span>
              </>
            )}
          </div>
          <div className="flex items-center gap-1">
            {user && (
              <span className="text-sm text-gray-500 hidden md:block mr-2">
                Hi, {user.display_name}
              </span>
            )}
            {isParent() && (
              <>
                <Link to="/parent/dashboard" className="p-2 rounded-lg hover:bg-gray-100 text-gray-600" title="Dashboard">
                  <LayoutDashboard size={20} />
                </Link>
                <Link to="/parent/textbooks" className="p-2 rounded-lg hover:bg-gray-100 text-gray-600" title="Textbooks">
                  <BookOpen size={20} />
                </Link>
                <Link to="/parent/settings" className="p-2 rounded-lg hover:bg-gray-100 text-gray-600" title="Settings">
                  <Settings size={20} />
                </Link>
                <button onClick={handleLogout} className="p-2 rounded-lg hover:bg-gray-100 text-gray-600" title="Logout">
                  <LogOut size={20} />
                </button>
              </>
            )}
            {user?.role === 'child' && (
              <>
                <Link to="/child/home" className="p-2 rounded-lg hover:bg-gray-100 text-gray-600" title="Home">
                  <Home size={20} />
                </Link>
                <Link to="/child/self-assign" className="p-2 rounded-lg hover:bg-gray-100 text-purple-500" title="Create Practice">
                  <PlusCircle size={20} />
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-5xl mx-auto w-full px-4 py-6">
        {children}
      </main>
    </div>
  )
}
