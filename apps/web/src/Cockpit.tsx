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
  const executions = useQuery({ queryKey: ['executions', id], queryFn: () => api.executions(id!), enabled: Boolean(id) })
  const artifacts = useQuery({ queryKey: ['artifacts', id], queryFn: () => api.artifacts(id!), enabled: Boolean(id) })
  const needsRecovery = task.data?.state === 'failed' && task.data.steps.some(step => step.state === 'needs_review')
  const recovery = useQuery({ queryKey: ['recovery', id], queryFn: () => api.recovery(id!), enabled: Boolean(id && needsRecovery) })
  const decision = useMutation({ mutationFn: ({ approval, value }: { approval: Approval; value: 'approved' | 'rejected' }) => api.decide(approval, value), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['task', id] }); queryClient.invalidateQueries({ queryKey: ['approvals'] }) } })
  const cancel = useMutation({ mutationFn: () => api.cancelTask(id!), onSuccess: () => queryClient.invalidateQueries({ queryKey: ['task', id] }) })
  const pause = useMutation({ mutationFn: () => api.pauseTask(id!), onSuccess: () => queryClient.invalidateQueries({ queryKey: ['task', id] }) })
  const resume = useMutation({ mutationFn: () => api.resumeTask(id!), onSuccess: () => queryClient.invalidateQueries({ queryKey: ['task', id] }) })
  const resolveRecovery = useMutation({ mutationFn: (value: 'accept_existing' | 'confirm_absent') => api.resolveRecovery(id!, recovery.data!, value), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['task', id] }); queryClient.invalidateQueries({ queryKey: ['recovery', id] }); queryClient.invalidateQueries({ queryKey: ['artifacts', id] }); queryClient.invalidateQueries({ queryKey: ['journal', id] }); queryClient.invalidateQueries({ queryKey: ['executions', id] }) } })

  useEffect(() => {
    if (!id || terminal) return
    const events = new EventSource(`/api/v1/tasks/${id}/events`)
    const update = () => {
      queryClient.invalidateQueries({ queryKey: ['task', id] })
      queryClient.invalidateQueries({ queryKey: ['journal', id] })
      queryClient.invalidateQueries({ queryKey: ['executions', id] })
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
    {needsRecovery && <section className="approval-panel"><h2>Report recovery required</h2>{recovery.isLoading ? <p>Inspecting the report file…</p> : recovery.isError ? <p role="alert">{recovery.error.message}</p> : recovery.data && <><p>The worker stopped during a report write. NEXUS will not repeat this action automatically.</p><p><strong>{recovery.data.filename}</strong> · {recovery.data.status === 'matches' ? 'File matches the expected report' : recovery.data.status === 'absent' ? 'No report file was found' : 'File needs operator inspection'}</p><small>Expected SHA-256: {recovery.data.expected_sha256}{recovery.data.actual_sha256 && ` · Found: ${recovery.data.actual_sha256}`}</small><div className="recovery-actions">{recovery.data.status === 'matches' && <button className="button" onClick={() => resolveRecovery.mutate('accept_existing')} disabled={resolveRecovery.isPending}>Accept verified report</button>}{recovery.data.status === 'absent' && <button className="button" onClick={() => resolveRecovery.mutate('confirm_absent')} disabled={resolveRecovery.isPending}>Confirm report absent</button>}{['mismatch', 'unsafe'].includes(recovery.data.status) && <p role="alert">The saved file differs from the expected report or has an unsafe path. Inspect the local data directory before resolving this task.</p>}</div></>}</section>}
    {(decision.isError || cancel.isError || pause.isError || resume.isError || resolveRecovery.isError) && <p role="alert" className="form-error">{decision.error?.message || cancel.error?.message || pause.error?.message || resume.error?.message || resolveRecovery.error?.message}</p>}
    <section className="empty-panel"><h2>Steps</h2><ol className="timeline">{task.data.steps.map(step => <li key={step.id}><span>{step.description}</span><span className={`chip ${step.state}`}>{step.state}</span></li>)}</ol></section>
    <section className="empty-panel"><h2>Execution journal</h2>{journal.isLoading ? <p>Loading events…</p> : journal.isError ? <p role="alert">{journal.error.message}</p> : <ol className="journal">{journal.data?.map(event => {
      const result = event.payload.result as { matches?: { source: string; line: number; excerpt: string }[]; truncated?: boolean } | undefined
      return <li key={event.id}><time dateTime={event.occurred_at}>{new Date(event.occurred_at).toLocaleString()}</time><strong>{eventLabel(event)}</strong>{event.payload.tool_name === 'search_local_docs' && result?.matches && <details><summary>{result.matches.length} source matches{result.truncated ? ' (limit reached)' : ''}</summary><ul>{result.matches.map((match, index) => <li key={`${match.source}-${match.line}-${index}`}><strong>{match.source}:{match.line}</strong> {match.excerpt}</li>)}</ul></details>}</li>
    })}</ol>}</section>
    <section className="empty-panel"><h2>Tool receipts</h2>{executions.isLoading ? <p>Loading tool receipts…</p> : executions.isError ? <p role="alert">{executions.error.message}</p> : executions.data?.length ? <ol className="receipt-list">{executions.data.map(item => <li key={item.id}><details><summary>Step {item.step_ordinal}: {item.tool_name} v{item.tool_version} · attempt {item.attempt} · {item.status}</summary><dl><dt>Started</dt><dd>{item.started_at ? new Date(item.started_at).toLocaleString() : 'Pending'}</dd><dt>Ended</dt><dd>{item.ended_at ? new Date(item.ended_at).toLocaleString() : 'Pending'}</dd><dt>Arguments SHA-256</dt><dd>{item.args_hash}</dd><dt>Idempotency key</dt><dd>{item.idempotency_key}</dd>{item.error_code && <><dt>Error code</dt><dd>{item.error_code}</dd></>}</dl>{item.result && <pre>{JSON.stringify(item.result, null, 2)}</pre>}</details></li>)}</ol> : <p>No tool has started yet.</p>}</section>
    <section className="empty-panel"><h2>Artifacts</h2>{artifacts.data?.length ? <ul className="artifact-list">{artifacts.data.map(item => <li key={item.id}><a href={`/api/v1/artifacts/${item.id}`}>{item.filename}</a><small>{item.size_bytes} bytes · SHA-256 {item.sha256}</small></li>)}</ul> : <p>No report has been written yet.</p>}</section>
  </main>
}
