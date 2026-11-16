import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from './api'

export function Artifacts() {
  const [offset, setOffset] = useState(0)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const artifacts = useQuery({ queryKey: ['artifact-library', offset], queryFn: () => api.artifactLibrary(offset) })
  const preview = useQuery({ queryKey: ['artifact-preview', selectedId], queryFn: () => api.artifactText(selectedId!), enabled: Boolean(selectedId) })
  const selected = artifacts.data?.items.find(item => item.id === selectedId)
  return <main>
    <div className="page-heading"><p className="kicker">Verified outputs</p><h1>Artifacts.</h1><p>Find reports created by approved tasks. Downloads are checked against their recorded SHA-256 digest.</p></div>
    <section className="empty-panel"><h2>Files</h2>{artifacts.isLoading ? <p>Loading artifacts…</p> : artifacts.isError ? <p role="alert">{artifacts.error.message}</p> : artifacts.data?.items.length ? <><ul className="history-list">{artifacts.data.items.map(item => <li key={item.id}><button className="text-button" onClick={() => setSelectedId(item.id)} aria-label={`Preview ${item.filename}`}>{item.filename}</button><span>{(item.size_bytes / 1024).toFixed(1)} KiB · {new Date(item.created_at).toLocaleString()}</span><small>From <Link to={`/tasks/${item.task_id}/run`}>{item.task_goal}</Link></small></li>)}</ul><div className="pager"><button className="text-button" disabled={offset === 0} onClick={() => { setSelectedId(null); setOffset(Math.max(0, offset - 20)) }}>Previous</button><span>{offset + 1}–{offset + artifacts.data.items.length} of {artifacts.data.total}</span><button className="text-button" disabled={offset + 20 >= artifacts.data.total} onClick={() => { setSelectedId(null); setOffset(offset + 20) }}>Next</button></div></> : <p>No artifacts yet. Complete an approved task to create one.</p>}</section>
    {selected && <section className="empty-panel"><div className="page-heading"><h2>Report preview: {selected.filename}</h2><p>Verified SHA-256: <code>{selected.sha256}</code></p><p><a href={`/api/v1/artifacts/${selected.id}`}>Download report</a> · <Link to={`/tasks/${selected.task_id}/run`}>Open source task</Link></p></div>{preview.isLoading ? <p>Loading preview…</p> : preview.isError ? <p role="alert">{preview.error.message}</p> : <pre className="artifact-preview">{preview.data}</pre>}</section>}
  </main>
}
