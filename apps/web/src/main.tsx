import React, { useState } from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider, useMutation, useQuery } from '@tanstack/react-query'
import { BrowserRouter, Link, Route, Routes, useNavigate, useParams } from 'react-router-dom'
import { api, type Step, type TaskDraft } from './api'
import { Cockpit } from './Cockpit'
import { History } from './History'
import './styles.css'

const queryClient = new QueryClient()
const Status = ({ state }: { state: string }) => <span className={`chip ${state}`}>{state.replace('_', ' ')}</span>

function Dashboard() {
  const health = useQuery({ queryKey: ['health'], queryFn: async () => { const response = await fetch('/health'); if (!response.ok) throw new Error('API unavailable'); return response.json() as Promise<{ status: string }> }, retry: false, refetchInterval: 15000 })
  const tasks = useQuery({ queryKey: ['tasks'], queryFn: () => api.listTasks() })
  const model = useQuery({ queryKey: ['model'], queryFn: api.modelStatus, retry: false })
  const worker = useQuery({ queryKey: ['worker'], queryFn: api.workerStatus, retry: false, refetchInterval: 5000 })
  return <main>
    <div className="page-heading"><p className="kicker">Workspace overview</p><h1>Make every action visible.</h1><p>Plan, approve, and verify local AI workflows from one place.</p></div>
    <div className="overview-grid"><section className="feature-panel"><h2>Start with an objective</h2><p>Describe the outcome you want. NEXUS will prepare a reviewable plan before taking action.</p><Link className="button" to="/tasks/new">Create task</Link></section><section className="status-panel"><h2>System status</h2><div className="status-row"><span>API</span><strong className={health.isSuccess ? 'good' : 'muted'}>{health.isLoading ? 'Checking…' : health.isSuccess ? 'Online' : 'Unavailable'}</strong></div><div className="status-row"><span>Worker</span><strong className={worker.data?.active ? 'good' : 'muted'}>{worker.isLoading ? 'Checking…' : worker.data?.active ? 'Online' : 'Offline'}</strong></div><div className="status-row"><span>Local model</span><strong className={model.data?.available ? 'good' : 'muted'}>{model.isLoading ? 'Checking…' : model.data?.available ? model.data.model : 'Unavailable'}</strong></div><p className="help-text">{model.data?.message || 'Demo mode works without a local model'}. {worker.data?.active ? 'The worker is ready for approved plans.' : 'Run the worker to execute approved plans.'}</p></section></div>
    <section className="empty-panel"><h2>Recent tasks</h2>{tasks.isLoading ? <p>Loading tasks…</p> : tasks.isError ? <p role="alert">{tasks.error.message}</p> : tasks.data?.items.length ? <ul className="task-list">{tasks.data.items.map(task => <li key={task.id}><Link to={["draft", "review_required"].includes(task.state) ? `/tasks/${task.id}/plan` : `/tasks/${task.id}/run`}>{task.goal}</Link><Status state={task.state} /></li>)}</ul> : <p>No tasks yet. Create one to begin a tracked workflow.</p>}</section>
  </main>
}

function NewTask() {
  const navigate = useNavigate()
  const [goal, setGoal] = useState('Read the sample project notes and generate a structured report.')
  const [constraints, setConstraints] = useState('')
  const [success, setSuccess] = useState('A Markdown report with findings and source references.')
  const [workspace, setWorkspace] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [inputError, setInputError] = useState('')
  const mutation = useMutation({ mutationFn: api.createTask, onSuccess: task => { queryClient.invalidateQueries({ queryKey: ['tasks'] }); navigate(`/tasks/${task.id}/plan`) } })
  async function submit(event: React.FormEvent) { event.preventDefault(); setInputError(''); if (workspace && files.length) { setInputError('Choose a folder or attach files, not both.'); return } if (files.length > 5 || files.some(file => file.size > 65536 || !/^[a-zA-Z0-9_-]+\.(md|txt)$/.test(file.name))) { setInputError('Attach up to five Markdown or text files, each at most 64 KiB, with simple names.'); return } const input_files = await Promise.all(files.map(async file => ({ name: file.name, content: await file.text() }))); const draft: TaskDraft = { goal, constraints: constraints.split('\n').map(value => value.trim()).filter(Boolean), success_criteria: success || null, capabilities: ['read_file', 'write_report'], network_access: false, workspace_path: workspace || null, input_files }; mutation.mutate(draft) }
  return <main><div className="page-heading"><p className="kicker">New task</p><h1>Define the objective.</h1><p>Review your plan before any tools run. This demo uses synthetic notes and keeps network access off.</p></div><form className="form-panel" onSubmit={submit}>
    <label htmlFor="goal">Goal</label><textarea id="goal" rows={4} required minLength={8} maxLength={4000} value={goal} onChange={event => setGoal(event.target.value)} />
    <label htmlFor="constraints">Constraints <span className="optional">one per line, optional</span></label><textarea id="constraints" rows={3} value={constraints} onChange={event => setConstraints(event.target.value)} placeholder="Use only the supplied sample notes" />
    <label htmlFor="success">Success criteria</label><textarea id="success" rows={2} value={success} onChange={event => setSuccess(event.target.value)} />
    <label htmlFor="workspace">Approved workspace folder <span className="optional">optional, configured by the operator</span></label><input id="workspace" value={workspace} onChange={event => setWorkspace(event.target.value)} placeholder="C:\\Projects\\Notes" />
    <label htmlFor="files">Supporting files <span className="optional">up to five .md or .txt files</span></label><input id="files" type="file" accept=".md,.txt" multiple onChange={event => setFiles(Array.from(event.target.files || []))} />
    <div className="scope-note"><strong>Task scope</strong><p>{workspace ? 'Read the approved folder' : files.length ? `Read ${files.length} attached file(s)` : 'Read two supplied demo notes'} · Write a Markdown report after approval · No network access</p></div>
    {inputError && <p className="form-error" role="alert">{inputError}</p>}
    {mutation.isError && <p className="form-error" role="alert">{mutation.error.message}</p>}
    <button className="button" disabled={mutation.isPending}>{mutation.isPending ? 'Creating…' : 'Create task'}</button>
  </form></main>
}

function PlanReview() {
  const { id } = useParams()
  const navigate = useNavigate()
  const task = useQuery({ queryKey: ['task', id], queryFn: () => api.getTask(id!), enabled: Boolean(id) })
  const [draft, setDraft] = useState<Step[] | null>(null)
  const [notice, setNotice] = useState('')
  const [mode, setMode] = useState<'demo' | 'ollama'>('demo')
  const plan = useMutation({ mutationFn: () => api.planTask(id!, mode), onSuccess: result => { queryClient.setQueryData(['task', id], result); setDraft(null); setNotice('Plan generated.') } })
  const save = useMutation({ mutationFn: () => api.editPlan(task.data!, draft!), onSuccess: result => { queryClient.setQueryData(['task', id], result); setDraft(null); setNotice('Plan saved. Any earlier approvals require renewal.') } })
  const start = useMutation({ mutationFn: () => api.startTask(id!), onSuccess: () => navigate(`/tasks/${id}/run`) })
  if (task.isLoading) return <main><p>Loading plan…</p></main>
  if (task.isError || !task.data) return <main><p role="alert">{task.error?.message || 'Task not found'}</p></main>
  const steps = draft ?? task.data.steps
  function updateStep(index: number, changes: Partial<Step>) { setDraft(steps.map((step, i) => i === index ? { ...step, ...changes } : step)) }
  function move(index: number, direction: number) { const next = [...steps]; const target = index + direction; if (target < 0 || target >= next.length || steps[index].dependencies.length || steps[target].dependencies.length) return; [next[index], next[target]] = [next[target], next[index]]; setDraft(next) }
  return <main><div className="page-heading"><p className="kicker"><Link to="/">Overview</Link> / Plan review</p><h1>Review the steps.</h1><p>{task.data.goal}</p></div><div className="review-head"><Status state={task.data.state} /><span>Version {task.data.plan_version}</span></div>
    {notice && <p className="notice" role="status">{notice}</p>}
    <div className="mode-picker"><label htmlFor="planning-mode">Planning mode</label><select id="planning-mode" value={mode} disabled={task.data.state !== 'review_required' && task.data.state !== 'draft'} onChange={event => setMode(event.target.value as 'demo' | 'ollama')}><option value="demo">Deterministic demo</option><option value="ollama">Local Ollama model</option></select></div>
    {!steps.length ? <section className="empty-panel"><h2>No plan yet</h2><p>Generate a reviewable plan using the selected mode.</p><button className="button" onClick={() => plan.mutate()} disabled={plan.isPending}>{plan.isPending ? 'Generating…' : 'Generate plan'}</button></section> : <section className="steps" aria-label="Plan steps">{steps.map((step, index) => <article className="step-card" key={step.id}><div className="step-number">{index + 1}</div><div className="step-body"><label htmlFor={`description-${step.id}`}>Step description</label><input id={`description-${step.id}`} value={step.description} readOnly={task.data.state !== 'review_required'} onChange={event => updateStep(index, { description: event.target.value })} /><div className="step-meta"><span>{step.tool_name.replace('_', ' ')}</span><span>{step.risk_level} risk</span>{step.dependencies.length > 0 && <span>After steps {step.dependencies.join(', ')}</span>}</div><label htmlFor={`arg-${step.id}`}>{step.tool_name === 'read_file' ? 'Relative file path' : 'Report filename'}</label><input id={`arg-${step.id}`} value={step.tool_name === 'read_file' ? step.args.path || '' : step.args.filename || ''} readOnly={task.data.state !== 'review_required'} onChange={event => updateStep(index, { args: step.tool_name === 'read_file' ? { path: event.target.value } : { filename: event.target.value } })} /><div className="reorder"><button type="button" onClick={() => move(index, -1)} disabled={task.data.state !== 'review_required' || index === 0 || step.dependencies.length > 0 || steps[index - 1]?.dependencies.length > 0} aria-label={`Move step ${index + 1} up`}>Move up</button><button type="button" onClick={() => move(index, 1)} disabled={task.data.state !== 'review_required' || index === steps.length - 1 || step.dependencies.length > 0 || steps[index + 1]?.dependencies.length > 0} aria-label={`Move step ${index + 1} down`}>Move down</button></div></div></article>)}<div className="plan-actions"><button className="button" disabled={task.data.state !== 'review_required' || !draft || save.isPending} onClick={() => save.mutate()}>{save.isPending ? 'Saving…' : 'Save plan'}</button><button className="text-button" onClick={() => plan.mutate()} disabled={task.data.state !== 'review_required' || plan.isPending}>Regenerate</button></div><p className="help-text">{task.data.state === 'review_required' ? 'Save any edits before starting. The report write requires a separate approval.' : 'This plan is locked after execution starts.'}</p></section>}
    {task.data.state === 'review_required' && steps.length > 0 && <button className="button" disabled={Boolean(draft) || start.isPending} onClick={() => start.mutate()}>{start.isPending ? 'Starting…' : 'Start approved plan'}</button>}
    {task.data.state !== 'draft' && task.data.state !== 'review_required' && <Link className="button" to={`/tasks/${id}/run`}>View execution</Link>}
    {(plan.isError || save.isError || start.isError) && <p className="form-error" role="alert">{plan.error?.message || save.error?.message || start.error?.message}</p>}
  </main>
}

function App() { return <div className="app-shell"><aside className="sidebar"><Link to="/" className="brand"><span className="brand-mark">N</span><span>NEXUS<small>Local operations</small></span></Link><nav aria-label="Primary navigation"><Link to="/">Overview</Link><Link to="/tasks/new">New task</Link><Link to="/history">History</Link></nav><div className="sidebar-foot">Local-first · Synthetic demo</div></aside><Routes><Route path="/" element={<Dashboard />} /><Route path="/tasks/new" element={<NewTask />} /><Route path="/tasks/:id/plan" element={<PlanReview />} /><Route path="/tasks/:id/run" element={<Cockpit />} /><Route path="/history" element={<History />} /></Routes></div> }

ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><QueryClientProvider client={queryClient}><BrowserRouter><App /></BrowserRouter></QueryClientProvider></React.StrictMode>)
