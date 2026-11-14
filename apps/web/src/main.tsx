import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query'
import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import './styles.css'

const queryClient = new QueryClient()

function Dashboard() {
  const health = useQuery({
    queryKey: ['health'],
    queryFn: async () => {
      const response = await fetch('/health')
      if (!response.ok) throw new Error('The API is unavailable')
      return response.json() as Promise<{ status: string }>
    },
    retry: false,
    refetchInterval: 15000,
  })
  return <main>
    <div className="page-heading"><p className="kicker">Workspace overview</p><h1>Make every action visible.</h1><p>Plan, approve, and verify local AI workflows from one place.</p></div>
    <div className="overview-grid">
      <section className="feature-panel"><h2>Start with an objective</h2><p>Describe the outcome you want. NEXUS will prepare a reviewable plan before taking action.</p><Link className="button" to="/tasks/new">Create task</Link></section>
      <section className="status-panel"><h2>System status</h2><div className="status-row"><span>API</span><strong className={health.isSuccess ? 'good' : 'muted'}>{health.isLoading ? 'Checking…' : health.isSuccess ? 'Online' : 'Unavailable'}</strong></div><div className="status-row"><span>Planning</span><strong>Demo mode</strong></div><p className="help-text">Operational data will appear here as each service becomes available.</p></section>
    </div>
    <section className="empty-panel"><h2>Recent tasks</h2><p>No tasks yet. Create one to begin a tracked workflow.</p></section>
  </main>
}

function NewTask() {
  return <main><div className="page-heading"><p className="kicker">New task</p><h1>Define the objective.</h1><p>Task creation becomes available with the planning service.</p></div><section className="empty-panel"><label htmlFor="goal">Goal</label><textarea id="goal" rows={5} disabled placeholder="What would you like to accomplish?" /><p className="help-text">The backend currently provides foundation and health checks. Execution is not enabled yet.</p></section></main>
}

function App() {
  return <div className="app-shell"><aside className="sidebar"><Link to="/" className="brand"><span className="brand-mark">N</span><span>NEXUS<small>Local operations</small></span></Link><nav aria-label="Primary navigation"><Link to="/">Overview</Link><Link to="/tasks/new">New task</Link></nav><div className="sidebar-foot">Local-first · Demo foundation</div></aside><Routes><Route path="/" element={<Dashboard />} /><Route path="/tasks/new" element={<NewTask />} /></Routes></div>
}

ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><QueryClientProvider client={queryClient}><BrowserRouter><App /></BrowserRouter></QueryClientProvider></React.StrictMode>)
