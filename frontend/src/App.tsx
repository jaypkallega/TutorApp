import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import api from './api/client'

import SetupPage from './pages/SetupPage'
import ParentLoginPage from './pages/ParentLoginPage'
import ParentDashboard from './pages/parent/Dashboard'
import SettingsPage from './pages/parent/Settings'
import TextbookLibrary from './pages/parent/TextbookLibrary'
import AssignmentBuilder from './pages/parent/AssignmentBuilder'
import ChildHome from './pages/child/Home'
import LearnMode from './pages/child/LearnMode'
import SolveWorkspace from './pages/child/SolveWorkspace'
import Results from './pages/child/Results'
import SelfAssign from './pages/child/SelfAssign'
import TeachMode from './pages/child/TeachMode'

function AppRouter() {
  const [setupComplete, setSetupComplete] = useState<boolean | null>(null)

  useEffect(() => {
    api.get('/auth/status')
      .then(r => setSetupComplete(r.data.setup_complete))
      .catch(() => setSetupComplete(false))
  }, [])

  if (setupComplete === null) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-primary-500 text-lg font-medium">Loading MathTutor...</div>
      </div>
    )
  }

  if (!setupComplete) {
    return (
      <Routes>
        <Route path="*" element={<SetupPage />} />
      </Routes>
    )
  }

  return (
    <Routes>
      <Route path="/setup" element={<Navigate to="/child/home" />} />
      <Route path="/parent/login" element={<ParentLoginPage />} />
      <Route path="/parent/dashboard" element={<ParentDashboard />} />
      <Route path="/parent/settings" element={<SettingsPage />} />
      <Route path="/parent/textbooks" element={<TextbookLibrary />} />
      <Route path="/parent/assignments/new" element={<AssignmentBuilder />} />
      <Route path="/child/home" element={<ChildHome />} />
      <Route path="/child/learn/:chapterId" element={<LearnMode />} />
      <Route path="/child/solve/:assignmentId" element={<SolveWorkspace />} />
      <Route path="/child/results/:submissionId" element={<Results />} />
      <Route path="/child/self-assign" element={<SelfAssign />} />
      <Route path="/child/teach/:chapterId" element={<TeachMode />} />
      <Route path="/" element={<Navigate to="/child/home" />} />
      <Route path="*" element={<Navigate to="/child/home" />} />
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AppRouter />
    </BrowserRouter>
  )
}
