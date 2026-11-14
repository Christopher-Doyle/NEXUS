import { useState, type FormEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from './api'

const STATES = ['draft', 'planning', 'review_required', 'queued', 'running', 'waiting_approval', 'pausing', 'paused', 'failed', 'cancelled', 'completed']

export function History() {
  const [searchInput, setSearchInput] = useState('')
  const [stateInput, setStateInput] = useState('')
  const [q, setQ] = useState('')
  const [state, setState] = useState('')
  const [offset, setOffset] = useState(0)
  const tasks = useQuery({ queryKey: ['history', q, state, offset], queryFn: () => api.listTasks({ q, state, offset }) })
  function submit(event: FormEvent) { event.preventDefault(); setQ(searchInput.trim()); setState(stateInput); setOffset(0) }
  return <main><div className="page-heading"><p className="kicker">Task history</p><h1>Trace every run.</h1><p>Search persisted tasks, inspect outcomes and reopen the execution record.</p></div>
    <form className="history-filter" onSubmit={submit}><label htmlFor="history-search">Search goals</label><input id="history-search" value={searchInput} maxLength={100} onChange={event => setSearchInput(event.target.value)} placeholder="Project notes" /><label htmlFor="history-state">Status</label><select id="history-state" value={stateInput} onChange={event => setStateInput(event.target.value)}><option value="">All statuses</option>{STATES.map(value => <option key={value} value={value}>{value.replace('_', ' ')}</option>)}</select><button className="button">Search</button></form>
    <section className="empty-panel"><h2>Tasks</h2>{tasks.isLoading ? <p>Loading history…</p> : tasks.isError ? <p role="alert">{tasks.error.message}</p> : tasks.data?.items.length ? <><ul className="history-list">{tasks.data.items.map(task => <li key={task.id}><Link to={`/tasks/${task.id}/${['draft', 'review_required'].includes(task.state) ? 'plan' : 'run'}`}>{task.goal}</Link><span className={`chip ${task.state}`}>{task.state.replace('_', ' ')}</span><small>Created {new Date(task.created_at).toLocaleString()}{task.completed_at ? ` · Ended ${new Date(task.completed_at).toLocaleString()}` : ''}</small></li>)}</ul><div className="pager"><button className="text-button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 20))}>Previous</button><span>{offset + 1}–{offset + tasks.data.items.length} of {tasks.data.total}</span><button className="text-button" disabled={offset + 20 >= tasks.data.total} onClick={() => setOffset(offset + 20)}>Next</button></div></> : <p>No tasks match these filters. Try a different search or create a task.</p>}</section>
  </main>
}
