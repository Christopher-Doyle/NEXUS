export type Step = { id: string; ordinal: number; description: string; tool_name: 'read_file' | 'search_local_docs' | 'write_report' | 'fetch_url'; args: { path?: string; query?: string; filename?: string; url?: string }; args_hash: string; risk_level: string; state: string; dependencies: number[] }
export type Task = { id: string; goal: string; constraints: string[]; success_criteria: string | null; capabilities: string[]; network_access: boolean; workspace_path: string | null; input_files: string[]; state: string; plan_version: number; created_at: string; updated_at: string; completed_at: string | null; deadline_at: string | null; steps: Step[] }
export type TaskDraft = { goal: string; constraints: string[]; success_criteria: string | null; capabilities: ('read_file' | 'search_local_docs' | 'write_report' | 'fetch_url')[]; network_access: boolean; workspace_path: string | null; input_files: { name: string; content: string }[] }
export type Approval = { id: string; task_id: string; step_id: string; scope_hash: string; requested_action: string; decision: string; expires_at: string | null }
export type JournalEvent = { id: number; type: string; occurred_at: string; payload: Record<string, unknown> }
export type Artifact = { id: string; filename: string; sha256: string; size_bytes: number; media_type: string; created_at: string }
export type ArtifactRecord = Artifact & { task_id: string; task_goal: string }
export type LocalSettings = { ollama_model: string; ollama_timeout_seconds: number; task_timeout_seconds: number; retention_days: number; approved_workspace_count: number; network_access_enabled: boolean }
export type Recovery = { step_id: string; filename: string; status: 'matches' | 'absent' | 'mismatch' | 'unsafe'; expected_sha256: string; actual_sha256: string | null }
export type ExecutionReceipt = { id: string; step_id: string; step_ordinal: number; tool_name: string; tool_version: string; args_hash: string; idempotency_key: string; attempt: number; status: string; started_at: string | null; ended_at: string | null; lease_until: string | null; error_code: string | null; result: Record<string, unknown> | null }

async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch(`/api/v1${path}`, { method, headers: { 'Content-Type': 'application/json', 'X-Nexus-Intent': 'local' }, body: body === undefined ? undefined : JSON.stringify(body) })
  if (!response.ok) {
    const error: { detail?: string | { msg: string }[]; message?: string; fields?: { field: string; message: string }[]; correlation_id?: string } = await response.json()
    const detail = Array.isArray(error.detail) ? error.detail.map(item => item.msg).join(', ') : error.detail
    const fields = error.fields?.map(item => `${item.field}: ${item.message}`).join('; ')
    const message = fields || detail || error.message || `Request failed (${response.status})`
    throw new Error(response.status >= 500 && error.correlation_id ? `${message} (reference ${error.correlation_id})` : message)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const api = {
  listTasks: (filters?: { q?: string; state?: string; offset?: number }) => {
    const params = new URLSearchParams()
    if (filters?.q) params.set('q', filters.q)
    if (filters?.state) params.set('state', filters.state)
    if (filters?.offset) params.set('offset', String(filters.offset))
    return request<{ items: Task[]; total: number }>(`/tasks${params.size ? `?${params}` : ''}`)
  },
  getTask: (id: string) => request<Task>(`/tasks/${id}`),
  createTask: (draft: TaskDraft) => request<Task>('/tasks', 'POST', draft),
  deleteTask: (id: string) => request<void>(`/tasks/${id}`, 'DELETE', { confirm_id: id }),
  planTask: (id: string, mode: 'demo' | 'ollama') => request<Task>(`/tasks/${id}/plan`, 'POST', { mode }),
  modelStatus: () => request<{ available: boolean; model: string; message: string }>('/model/status'),
  workerStatus: () => request<{ active: boolean; active_count: number; last_seen_at: string | null }>('/worker/status'),
  settings: () => request<LocalSettings>('/settings'),
  updateSettings: (changes: Pick<LocalSettings, 'ollama_model' | 'ollama_timeout_seconds' | 'task_timeout_seconds' | 'retention_days'>) => request<LocalSettings>('/settings', 'PATCH', changes),
  editPlan: (task: Task, steps: Step[]) => request<Task>(`/tasks/${task.id}/steps`, 'PATCH', { plan_version: task.plan_version, steps: steps.map(({ description, tool_name, args, dependencies }) => ({ description, tool_name, args, dependencies })) }),
  startTask: (id: string) => request<Task>(`/tasks/${id}/start`, 'POST'),
  cancelTask: (id: string) => request<Task>(`/tasks/${id}/cancel`, 'POST'),
  pauseTask: (id: string) => request<Task>(`/tasks/${id}/pause`, 'POST'),
  resumeTask: (id: string) => request<Task>(`/tasks/${id}/resume`, 'POST'),
  approvals: () => request<Approval[]>('/approvals'),
  decide: (approval: Approval, decision: 'approved' | 'rejected') => request<Approval>(`/approvals/${approval.id}/decision`, 'POST', { decision, scope_hash: approval.scope_hash }),
  journal: async (id: string) => {
    const events: JournalEvent[] = []
    let after = 0
    for (;;) {
      const page = await request<JournalEvent[]>(`/tasks/${id}/journal?after=${after}`)
      events.push(...page)
      if (page.length < 500) return events
      if (events.length >= 10000) throw new Error('Journal exceeds the display limit')
      after = page[page.length - 1].id
    }
  },
  executions: (id: string) => request<ExecutionReceipt[]>(`/tasks/${id}/executions`),
  artifacts: (id: string) => request<Artifact[]>(`/tasks/${id}/artifacts`),
  exportTask: async (id: string) => {
    const [task, journal, executions, artifacts] = await Promise.all([
      api.getTask(id), api.journal(id), api.executions(id), api.artifacts(id),
    ])
    return { format: 'nexus-task-history-v1', exported_at: new Date().toISOString(), task, journal, executions, artifacts }
  },
  recovery: (id: string) => request<Recovery>(`/tasks/${id}/recovery`),
  resolveRecovery: (id: string, inspection: Recovery, decision: 'accept_existing' | 'confirm_absent') => request<{ task_state: string; step_state: string; decision: string }>(`/tasks/${id}/recovery`, 'POST', { step_id: inspection.step_id, expected_sha256: inspection.expected_sha256, decision }),
  artifactLibrary: (offset = 0) => request<{ items: ArtifactRecord[]; total: number }>(`/artifacts?offset=${offset}`),
  artifactText: async (id: string) => {
    const response = await fetch(`/api/v1/artifacts/${id}`)
    if (!response.ok) throw new Error(`Report preview unavailable (${response.status})`)
    const bytes = await response.arrayBuffer()
    if (bytes.byteLength > 512 * 1024) throw new Error('Report is too large to preview; download it instead')
    return new TextDecoder('utf-8', { fatal: true }).decode(bytes)
  },
}
