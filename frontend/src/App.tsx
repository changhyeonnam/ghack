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
      <footer className="site-foot">
        Demo cases use generated documents (synthetic data); no real customer data. Live AI analysis runs on Gemini within a
        fixed budget; cases analysed by visitors are shared read-only. LedgerLens drafts and challenges; a human decides.
      </footer>
    </div>
  )
}
