import React, { useState } from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider, useMutation, useQuery } from '@tanstack/react-query'
import { BrowserRouter, Link, Route, Routes, useNavigate, useParams } from 'react-router-dom'
import { api, type Step, type TaskDraft } from './api'
import './styles.css'

const queryClient = new QueryClient()
const Status = ({ state }: { state: string }) => <span className={`chip ${state}`}>{state.replace('_', ' ')}</span>

function Dashboard() {
  const health = useQuery({ queryKey: ['health'], queryFn: async () => { const response = await fetch('/health'); if (!response.ok) throw new Error('API unavailable'); return response.json() as Promise<{ status: string }> }, retry: false, refetchInterval: 15000 })
  const tasks = useQuery({ queryKey: ['tasks'], queryFn: api.listTasks })
  return <main>
    <div className="page-heading"><p className="kicker">Workspace overview</p><h1>Make every action visible.</h1><p>Plan, approve, and verify local AI workflows from one place.</p></div>
    <div className="overview-grid"><section className="feature-panel"><h2>Start with an objective</h2><p>Describe the outcome you want. NEXUS will prepare a reviewable plan before taking action.</p><Link className="button" to="/tasks/new">Create task</Link></section><section className="status-panel"><h2>System status</h2><div className="status-row"><span>API</span><strong className={health.isSuccess ? 'good' : 'muted'}>{health.isLoading ? 'Checking…' : health.isSuccess ? 'Online' : 'Unavailable'}</strong></div><div className="status-row"><span>Planning</span><strong>Demo mode</strong></div><p className="help-text">Demo plans use synthetic project notes. Tool execution is not enabled yet.</p></section></div>
    <section className="empty-panel"><h2>Recent tasks</h2>{tasks.isLoading ? <p>Loading tasks…</p> : tasks.isError ? <p role="alert">{tasks.error.message}</p> : tasks.data?.items.length ? <ul className="task-list">{tasks.data.items.map(task => <li key={task.id}><Link to={`/tasks/${task.id}/plan`}>{task.goal}</Link><Status state={task.state} /></li>)}</ul> : <p>No tasks yet. Create one to begin a tracked workflow.</p>}</section>
  </main>
}

function NewTask() {
  const navigate = useNavigate()
  const [goal, setGoal] = useState('Read the sample project notes and generate a structured report.')
  const [constraints, setConstraints] = useState('')
  const [success, setSuccess] = useState('A Markdown report with findings and source references.')
  const mutation = useMutation({ mutationFn: api.createTask, onSuccess: task => { queryClient.invalidateQueries({ queryKey: ['tasks'] }); navigate(`/tasks/${task.id}/plan`) } })
  function submit(event: React.FormEvent) { event.preventDefault(); const draft: TaskDraft = { goal, constraints: constraints.split('\n').map(value => value.trim()).filter(Boolean), success_criteria: success || null, capabilities: ['read_file', 'write_report'], network_access: false }; mutation.mutate(draft) }
  return <main><div className="page-heading"><p className="kicker">New task</p><h1>Define the objective.</h1><p>Review your plan before any tools run. This demo uses synthetic notes and keeps network access off.</p></div><form className="form-panel" onSubmit={submit}>
    <label htmlFor="goal">Goal</label><textarea id="goal" rows={4} required minLength={8} maxLength={4000} value={goal} onChange={event => setGoal(event.target.value)} />
    <label htmlFor="constraints">Constraints <span className="optional">one per line, optional</span></label><textarea id="constraints" rows={3} value={constraints} onChange={event => setConstraints(event.target.value)} placeholder="Use only the supplied sample notes" />
    <label htmlFor="success">Success criteria</label><textarea id="success" rows={2} value={success} onChange={event => setSuccess(event.target.value)} />
    <div className="scope-note"><strong>Task scope</strong><p>Read two supplied demo notes · Write a Markdown report after approval · No network access</p></div>
    {mutation.isError && <p className="form-error" role="alert">{mutation.error.message}</p>}
    <button className="button" disabled={mutation.isPending}>{mutation.isPending ? 'Creating…' : 'Create task'}</button>
  </form></main>
}

function PlanReview() {
  const { id } = useParams()
  const task = useQuery({ queryKey: ['task', id], queryFn: () => api.getTask(id!), enabled: Boolean(id) })
  const [draft, setDraft] = useState<Step[] | null>(null)
  const [notice, setNotice] = useState('')
  const plan = useMutation({ mutationFn: () => api.planTask(id!), onSuccess: result => { queryClient.setQueryData(['task', id], result); setDraft(null); setNotice('Plan generated.') } })
  const save = useMutation({ mutationFn: () => api.editPlan(task.data!, draft!), onSuccess: result => { queryClient.setQueryData(['task', id], result); setDraft(null); setNotice('Plan saved. Any earlier approvals require renewal.') } })
  if (task.isLoading) return <main><p>Loading plan…</p></main>
  if (task.isError || !task.data) return <main><p role="alert">{task.error?.message || 'Task not found'}</p></main>
  const steps = draft ?? task.data.steps
  function updateStep(index: number, changes: Partial<Step>) { setDraft(steps.map((step, i) => i === index ? { ...step, ...changes } : step)) }
  function move(index: number, direction: number) { const next = [...steps]; const target = index + direction; if (target < 0 || target >= next.length || steps[index].dependencies.length || steps[target].dependencies.length) return; [next[index], next[target]] = [next[target], next[index]]; setDraft(next) }
  return <main><div className="page-heading"><p className="kicker"><Link to="/">Overview</Link> / Plan review</p><h1>Review the steps.</h1><p>{task.data.goal}</p></div><div className="review-head"><Status state={task.data.state} /><span>Version {task.data.plan_version}</span></div>
    {notice && <p className="notice" role="status">{notice}</p>}
    {!steps.length ? <section className="empty-panel"><h2>No plan yet</h2><p>Generate a deterministic plan from the supplied demo notes.</p><button className="button" onClick={() => plan.mutate()} disabled={plan.isPending}>{plan.isPending ? 'Generating…' : 'Generate plan'}</button></section> : <section className="steps" aria-label="Plan steps">{steps.map((step, index) => <article className="step-card" key={step.id}><div className="step-number">{index + 1}</div><div className="step-body"><label htmlFor={`description-${step.id}`}>Step description</label><input id={`description-${step.id}`} value={step.description} onChange={event => updateStep(index, { description: event.target.value })} /><div className="step-meta"><span>{step.tool_name.replace('_', ' ')}</span><span>{step.risk_level} risk</span>{step.dependencies.length > 0 && <span>After steps {step.dependencies.join(', ')}</span>}</div><label htmlFor={`arg-${step.id}`}>{step.tool_name === 'read_file' ? 'Relative file path' : 'Report filename'}</label><input id={`arg-${step.id}`} value={step.tool_name === 'read_file' ? step.args.path || '' : step.args.filename || ''} onChange={event => updateStep(index, { args: step.tool_name === 'read_file' ? { path: event.target.value } : { filename: event.target.value } })} /><div className="reorder"><button type="button" onClick={() => move(index, -1)} disabled={index === 0 || step.dependencies.length > 0 || steps[index - 1]?.dependencies.length > 0} aria-label={`Move step ${index + 1} up`}>Move up</button><button type="button" onClick={() => move(index, 1)} disabled={index === steps.length - 1 || step.dependencies.length > 0 || steps[index + 1]?.dependencies.length > 0} aria-label={`Move step ${index + 1} down`}>Move down</button></div></div></article>)}<div className="plan-actions"><button className="button" disabled={!draft || save.isPending} onClick={() => save.mutate()}>{save.isPending ? 'Saving…' : 'Save plan'}</button><button className="text-button" onClick={() => plan.mutate()} disabled={plan.isPending}>Regenerate</button></div><p className="help-text">Execution is being built. Saving a plan does not run tools.</p></section>}
    {(plan.isError || save.isError) && <p className="form-error" role="alert">{plan.error?.message || save.error?.message}</p>}
  </main>
}

function App() { return <div className="app-shell"><aside className="sidebar"><Link to="/" className="brand"><span className="brand-mark">N</span><span>NEXUS<small>Local operations</small></span></Link><nav aria-label="Primary navigation"><Link to="/">Overview</Link><Link to="/tasks/new">New task</Link></nav><div className="sidebar-foot">Local-first · Synthetic demo</div></aside><Routes><Route path="/" element={<Dashboard />} /><Route path="/tasks/new" element={<NewTask />} /><Route path="/tasks/:id/plan" element={<PlanReview />} /></Routes></div> }

ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><QueryClientProvider client={queryClient}><BrowserRouter><App /></BrowserRouter></QueryClientProvider></React.StrictMode>)
