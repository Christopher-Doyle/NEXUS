import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from './api'

const STATES = ['draft', 'planning', 'review_required', 'queued', 'running', 'waiting_approval', 'pausing', 'paused', 'failed', 'cancelled', 'completed']

export function History() {
  const queryClient = useQueryClient()
  const [searchInput, setSearchInput] = useState('')
  const [stateInput, setStateInput] = useState('')
  const [q, setQ] = useState('')
  const [state, setState] = useState('')
  const [offset, setOffset] = useState(0)
  const tasks = useQuery({ queryKey: ['history', q, state, offset], queryFn: () => api.listTasks({ q, state, offset }) })
  const deletion = useMutation({ mutationFn: api.deleteTask, onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['history'] }); queryClient.invalidateQueries({ queryKey: ['tasks'] }); queryClient.invalidateQueries({ queryKey: ['artifact-library'] }) } })
  const [exportError, setExportError] = useState('')
  const [exporting, setExporting] = useState<string | null>(null)
  async function exportTask(id: string) {
    setExportError('')
    setExporting(id)
    try {
      const history = await api.exportTask(id)
      const url = URL.createObjectURL(new Blob([JSON.stringify(history, null, 2)], { type: 'application/json' }))
      const link = document.createElement('a')
      link.href = url
      link.download = `nexus-task-${id}.json`
      link.click()
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000)
    } catch (error) {
      setExportError(error instanceof Error ? error.message : 'Could not export task history')
    } finally {
      setExporting(null)
    }
  }
  function submit(event: FormEvent) { event.preventDefault(); setQ(searchInput.trim()); setState(stateInput); setOffset(0) }
  return <main><div className="page-heading"><p className="kicker">Task history</p><h1>Trace every run.</h1><p>Search persisted tasks, inspect outcomes and reopen the execution record.</p></div>
    <form className="history-filter" onSubmit={submit}><label htmlFor="history-search">Search goals</label><input id="history-search" value={searchInput} maxLength={100} onChange={event => setSearchInput(event.target.value)} placeholder="Project notes" /><label htmlFor="history-state">Status</label><select id="history-state" value={stateInput} onChange={event => setStateInput(event.target.value)}><option value="">All statuses</option>{STATES.map(value => <option key={value} value={value}>{value.replace('_', ' ')}</option>)}</select><button className="button">Search</button></form>
    <section className="empty-panel"><h2>Tasks</h2>{deletion.isError && <p role="alert" className="form-error">{deletion.error.message}</p>}{exportError && <p role="alert" className="form-error">{exportError}</p>}{tasks.isLoading ? <p>Loading history…</p> : tasks.isError ? <p role="alert">{tasks.error.message}</p> : tasks.data?.items.length ? <><ul className="history-list">{tasks.data.items.map(task => <li key={task.id}><Link to={`/tasks/${task.id}/${['draft', 'review_required'].includes(task.state) ? 'plan' : 'run'}`}>{task.goal}</Link><span className={`chip ${task.state}`}>{task.state.replace('_', ' ')}</span><small>Created {new Date(task.created_at).toLocaleString()}{task.completed_at ? ` · Ended ${new Date(task.completed_at).toLocaleString()}` : ''}</small><button className="text-button" disabled={exporting !== null} aria-label={`Export history for ${task.goal}`} onClick={() => void exportTask(task.id)}>{exporting === task.id ? 'Exporting…' : 'Export history'}</button>{['draft', 'review_required', 'completed', 'failed', 'cancelled'].includes(task.state) && <button className="text-button" disabled={deletion.isPending} aria-label={`Delete ${task.goal}`} onClick={() => { if (window.confirm(`Permanently delete this task, its journal, inputs and artifacts?\n\n${task.goal}`)) deletion.mutate(task.id) }}>Delete task</button>}</li>)}</ul><div className="pager"><button className="text-button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 20))}>Previous</button><span>{offset + 1}–{offset + tasks.data.items.length} of {tasks.data.total}</span><button className="text-button" disabled={offset + 20 >= tasks.data.total} onClick={() => setOffset(offset + 20)}>Next</button></div></> : <p>No tasks match these filters. Try a different search or create a task.</p>}</section>
  </main>
}
