import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from './api'
import { reportDiff } from './reportDiff'

export function Artifacts() {
  const [offset, setOffset] = useState(0)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [leftId, setLeftId] = useState('')
  const [rightId, setRightId] = useState('')
  const artifacts = useQuery({ queryKey: ['artifact-library', offset], queryFn: () => api.artifactLibrary(offset) })
  const preview = useQuery({ queryKey: ['artifact-preview', selectedId], queryFn: () => api.artifactText(selectedId!), enabled: Boolean(selectedId) })
  const canCompare = Boolean(leftId && rightId && leftId !== rightId)
  const left = useQuery({ queryKey: ['artifact-preview', leftId], queryFn: () => api.artifactText(leftId), enabled: canCompare })
  const right = useQuery({ queryKey: ['artifact-preview', rightId], queryFn: () => api.artifactText(rightId), enabled: canCompare })
  const differences = left.data && right.data ? reportDiff(left.data, right.data) : undefined
  const selected = artifacts.data?.items.find(item => item.id === selectedId)
  return <main>
    <div className="page-heading"><p className="kicker">Verified outputs</p><h1>Artifacts.</h1><p>Find reports created by approved tasks. Downloads are checked against their recorded SHA-256 digest.</p></div>
    <section className="empty-panel"><h2>Files</h2>{artifacts.isLoading ? <p>Loading artifacts…</p> : artifacts.isError ? <p role="alert">{artifacts.error.message}</p> : artifacts.data?.items.length ? <><ul className="history-list">{artifacts.data.items.map(item => <li key={item.id}><button className="text-button" onClick={() => setSelectedId(item.id)} aria-label={`Preview ${item.filename}`}>{item.filename}</button><span>{(item.size_bytes / 1024).toFixed(1)} KiB · {new Date(item.created_at).toLocaleString()}</span><small>From <Link to={`/tasks/${item.task_id}/run`}>{item.task_goal}</Link></small></li>)}</ul><div className="pager"><button className="text-button" disabled={offset === 0} onClick={() => { setSelectedId(null); setLeftId(''); setRightId(''); setOffset(Math.max(0, offset - 20)) }}>Previous</button><span>{offset + 1}–{offset + artifacts.data.items.length} of {artifacts.data.total}</span><button className="text-button" disabled={offset + 20 >= artifacts.data.total} onClick={() => { setSelectedId(null); setLeftId(''); setRightId(''); setOffset(offset + 20) }}>Next</button></div></> : <p>No artifacts yet. Complete an approved task to create one.</p>}</section>
    {selected && <section className="empty-panel"><div className="page-heading"><h2>Report preview: {selected.filename}</h2><p>Verified SHA-256: <code>{selected.sha256}</code></p><p><a href={`/api/v1/artifacts/${selected.id}`}>Download report</a> · <Link to={`/tasks/${selected.task_id}/run`}>Open source task</Link></p></div>{preview.isLoading ? <p>Loading preview…</p> : preview.isError ? <p role="alert">{preview.error.message}</p> : <pre className="artifact-preview">{preview.data}</pre>}</section>}
    {artifacts.data && artifacts.data.items.length > 1 && <section className="empty-panel"><h2>Compare reports</h2><p>Compare two verified reports on this page. Added and removed lines are shown below.</p><div className="compare-controls"><label htmlFor="compare-before">Before</label><select id="compare-before" value={leftId} onChange={event => setLeftId(event.target.value)}><option value="">Choose a report</option>{artifacts.data.items.map(item => <option key={item.id} value={item.id}>{item.filename} — {item.task_goal}</option>)}</select><label htmlFor="compare-after">After</label><select id="compare-after" value={rightId} onChange={event => setRightId(event.target.value)}><option value="">Choose a report</option>{artifacts.data.items.map(item => <option key={item.id} value={item.id}>{item.filename} — {item.task_goal}</option>)}</select></div>{canCompare && (left.isLoading || right.isLoading ? <p>Loading comparison…</p> : left.isError || right.isError ? <p role="alert">{left.error?.message || right.error?.message}</p> : differences === null ? <p role="status">One report has more than 200 lines. Download both reports to compare them.</p> : <ol className="diff-list" aria-label="Report differences" tabIndex={0}>{differences?.map((line, index) => <li key={index} className={`diff-${line.kind}`}><span aria-hidden="true">{line.kind === 'added' ? '+' : line.kind === 'removed' ? '−' : ' '}</span><span className="sr-only">{line.kind === 'added' ? 'Added: ' : line.kind === 'removed' ? 'Removed: ' : 'Unchanged: '}</span><code>{line.text || ' '}</code></li>)}</ol>)}</section>}
  </main>
}
