import type { FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, type LocalSettings } from './api'

export function Settings() {
  const queryClient = useQueryClient()
  const settings = useQuery({ queryKey: ['settings'], queryFn: api.settings })
  const model = useQuery({ queryKey: ['model'], queryFn: api.modelStatus, retry: false })
  const save = useMutation({ mutationFn: api.updateSettings, onSuccess: value => { queryClient.setQueryData(['settings'], value); queryClient.invalidateQueries({ queryKey: ['model'] }) } })

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const changes: Pick<LocalSettings, 'ollama_model' | 'ollama_timeout_seconds' | 'task_timeout_seconds'> = {
      ollama_model: String(form.get('ollama_model') || '').trim(),
      ollama_timeout_seconds: Number(form.get('ollama_timeout_seconds')),
      task_timeout_seconds: Number(form.get('task_timeout_seconds')),
    }
    save.mutate(changes)
  }

  return <main>
    <div className="page-heading"><p className="kicker">Local configuration</p><h1>Settings.</h1><p>Choose a model and execution limits. Folder grants stay in the operator's local environment file.</p></div>
    {settings.isLoading ? <section className="empty-panel"><p>Loading settings…</p></section> : settings.isError || !settings.data ? <section className="empty-panel"><p role="alert">{settings.error?.message || 'Settings unavailable'}</p></section> : <>
      <form className="form-panel" key={`${settings.data.ollama_model}-${settings.data.ollama_timeout_seconds}-${settings.data.task_timeout_seconds}`} onSubmit={submit}>
        <label htmlFor="setting-model">Installed Ollama model <span className="optional">optional</span></label><input id="setting-model" name="ollama_model" defaultValue={settings.data.ollama_model} maxLength={100} placeholder="qwen3.5:9b" />
        <label htmlFor="setting-model-timeout">Model planning timeout, seconds</label><input id="setting-model-timeout" name="ollama_timeout_seconds" type="number" min={10} max={180} required defaultValue={settings.data.ollama_timeout_seconds} />
        <label htmlFor="setting-task-timeout">Task dispatch deadline, seconds</label><input id="setting-task-timeout" name="task_timeout_seconds" type="number" min={60} max={86400} required defaultValue={settings.data.task_timeout_seconds} />
        <p className="help-text">The deadline stops new tool actions after it expires. An action already in progress may finish.</p>
        {save.isError && <p role="alert" className="form-error">{save.error.message}</p>}{save.isSuccess && <p role="status" className="notice">Settings saved locally.</p>}
        <button className="button" disabled={save.isPending}>{save.isPending ? 'Saving…' : 'Save settings'}</button>
      </form>
      <section className="empty-panel"><h2>System boundaries</h2><div className="status-row"><span>Local model</span><strong className={model.data?.available ? 'good' : 'muted'}>{model.isLoading ? 'Checking…' : model.data?.available ? 'Ready' : 'Unavailable'}</strong></div><p>{model.data?.message || 'Demo planning works without a model.'}</p><p>{settings.data.approved_workspace_count} operator-approved workspace{settings.data.approved_workspace_count === 1 ? '' : 's'} configured. Network tools are disabled.</p></section>
    </>}
  </main>
}
