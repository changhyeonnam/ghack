import { Link, Navigate, Route, Routes } from 'react-router-dom'
import { EmptyState } from './components/Badges'
import { TopBar } from './components/Shell'
import CaseList from './pages/CaseList'
import NewCase from './pages/NewCase'
import Workbench from './pages/Workbench'

export default function App() {
  return (
    <div className="app">
      <TopBar />
      <Routes>
        <Route path="/" element={<CaseList />} />
        <Route path="/cases/new" element={<NewCase />} />
        <Route path="/cases/:id" element={<Workbench />} />
        <Route
          path="*"
          element={
            <div className="page narrow">
              <EmptyState
                icon="alert-circle"
                title="Page not found"
                hint={
                  <>
                    Redirecting to the <Link to="/">portfolio</Link>.
                  </>
                }
              />
              <Navigate to="/" replace />
            </div>
          }
        />
      </Routes>
    </div>
  )
}
