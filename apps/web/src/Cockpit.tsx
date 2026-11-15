import { useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { api, type Approval, type JournalEvent } from './api'

function eventLabel(event: JournalEvent): string {
  if (event.type === 'task_state') return `Task ${String(event.payload.state).replaceAll('_', ' ')}`
  if (event.type === 'step_completed') return `${String(event.payload.tool_name).replaceAll('_', ' ')} completed`
  if (event.type === 'approval_decided') return `Write ${String(event.payload.decision)}`
  if (event.type === 'task_timeout') return 'Task execution deadline reached'
  return event.type.replaceAll('_', ' ')
}

export function Cockpit() {
  const { id } = useParams()
  const queryClient = useQueryClient()
  const task = useQuery({ queryKey: ['task', id], queryFn: () => api.getTask(id!), enabled: Boolean(id) })
  const terminal = ['completed', 'failed', 'cancelled'].includes(task.data?.state || '')
  const approvals = useQuery({ queryKey: ['approvals'], queryFn: api.approvals, refetchInterval: terminal ? false : 5000 })
  const journal = useQuery({ queryKey: ['journal', id], queryFn: () => api.journal(id!), enabled: Boolean(id) })
  const artifacts = useQuery({ queryKey: ['artifacts', id], queryFn: () => api.artifacts(id!), enabled: Boolean(id) })
  const decision = useMutation({ mutationFn: ({ approval, value }: { approval: Approval; value: 'approved' | 'rejected' }) => api.decide(approval, value), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['task', id] }); queryClient.invalidateQueries({ queryKey: ['approvals'] }) } })
  const cancel = useMutation({ mutationFn: () => api.cancelTask(id!), onSuccess: () => queryClient.invalidateQueries({ queryKey: ['task', id] }) })
  const pause = useMutation({ mutationFn: () => api.pauseTask(id!), onSuccess: () => queryClient.invalidateQueries({ queryKey: ['task', id] }) })
  const resume = useMutation({ mutationFn: () => api.resumeTask(id!), onSuccess: () => queryClient.invalidateQueries({ queryKey: ['task', id] }) })

  useEffect(() => {
    if (!id || terminal) return
    const events = new EventSource(`/api/v1/tasks/${id}/events`)
    const update = () => {
      queryClient.invalidateQueries({ queryKey: ['task', id] })
      queryClient.invalidateQueries({ queryKey: ['journal', id] })
      queryClient.invalidateQueries({ queryKey: ['artifacts', id] })
      queryClient.invalidateQueries({ queryKey: ['approvals'] })
    }
    events.addEventListener('update', update)
    return () => { events.removeEventListener('update', update); events.close() }
  }, [id, queryClient, terminal])

  if (task.isLoading) return <main><p>Loading execution…</p></main>
  if (task.isError || !task.data) return <main><p role="alert">{task.error?.message || 'Task not found'}</p></main>
  const pending = approvals.data?.filter(item => item.task_id === id) || []
  return <main><div className="page-heading"><p className="kicker"><Link to="/">Overview</Link> / Execution</p><h1>Execution cockpit</h1><p>{task.data.goal}</p></div>
    <div className="cockpit-head"><span className={`chip ${task.data.state}`}>{task.data.state.replace('_', ' ')}</span>{task.data.deadline_at && !terminal && <small>Execution deadline: {new Date(task.data.deadline_at).toLocaleString()}</small>}<div className="cockpit-controls">{task.data.state === 'running' && <button className="text-button" onClick={() => pause.mutate()} disabled={pause.isPending}>Pause</button>}{task.data.state === 'paused' && <button className="text-button" onClick={() => resume.mutate()} disabled={resume.isPending}>Resume</button>}{!['completed', 'cancelled', 'failed'].includes(task.data.state) && <button className="text-button" onClick={() => cancel.mutate()} disabled={cancel.isPending}>Cancel task</button>}</div></div>
    {pending.length > 0 && <section className="approval-panel"><h2>Approval required</h2><p>Review each action before allowing a file write. Approval applies only to these exact step arguments.</p>{pending.map(item => <div className="approval-row" key={item.id}><strong>{item.requested_action}</strong><div><button className="button" onClick={() => decision.mutate({ approval: item, value: 'approved' })} disabled={decision.isPending}>Approve write</button><button className="text-button" onClick={() => decision.mutate({ approval: item, value: 'rejected' })} disabled={decision.isPending}>Reject</button></div></div>)}</section>}
    {(decision.isError || cancel.isError || pause.isError || resume.isError) && <p role="alert" className="form-error">{decision.error?.message || cancel.error?.message || pause.error?.message || resume.error?.message}</p>}
    <section className="empty-panel"><h2>Steps</h2><ol className="timeline">{task.data.steps.map(step => <li key={step.id}><span>{step.description}</span><span className={`chip ${step.state}`}>{step.state}</span></li>)}</ol></section>
    <section className="empty-panel"><h2>Execution journal</h2>{journal.isLoading ? <p>Loading events…</p> : journal.isError ? <p role="alert">{journal.error.message}</p> : <ol className="journal">{journal.data?.map(event => {
      const result = event.payload.result as { matches?: { source: string; line: number; excerpt: string }[]; truncated?: boolean } | undefined
      return <li key={event.id}><time dateTime={event.occurred_at}>{new Date(event.occurred_at).toLocaleString()}</time><strong>{eventLabel(event)}</strong>{event.payload.tool_name === 'search_local_docs' && result?.matches && <details><summary>{result.matches.length} source matches{result.truncated ? ' (limit reached)' : ''}</summary><ul>{result.matches.map((match, index) => <li key={`${match.source}-${match.line}-${index}`}><strong>{match.source}:{match.line}</strong> {match.excerpt}</li>)}</ul></details>}</li>
    })}</ol>}</section>
    <section className="empty-panel"><h2>Artifacts</h2>{artifacts.data?.length ? <ul className="artifact-list">{artifacts.data.map(item => <li key={item.id}><a href={`/api/v1/artifacts/${item.id}`}>{item.filename}</a><small>{item.size_bytes} bytes · SHA-256 {item.sha256}</small></li>)}</ul> : <p>No report has been written yet.</p>}</section>
  </main>
}
