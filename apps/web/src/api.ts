export type Step = { id: string; ordinal: number; description: string; tool_name: 'read_file' | 'search_local_docs' | 'write_report'; args: { path?: string; query?: string; filename?: string }; args_hash: string; risk_level: string; state: string; dependencies: number[] }
export type Task = { id: string; goal: string; constraints: string[]; success_criteria: string | null; capabilities: string[]; network_access: boolean; workspace_path: string | null; input_files: string[]; state: string; plan_version: number; created_at: string; updated_at: string; completed_at: string | null; deadline_at: string | null; steps: Step[] }
export type TaskDraft = { goal: string; constraints: string[]; success_criteria: string | null; capabilities: ('read_file' | 'search_local_docs' | 'write_report')[]; network_access: boolean; workspace_path: string | null; input_files: { name: string; content: string }[] }
export type Approval = { id: string; task_id: string; step_id: string; scope_hash: string; requested_action: string; decision: string; expires_at: string | null }
export type JournalEvent = { id: number; type: string; occurred_at: string; payload: Record<string, unknown> }
export type Artifact = { id: string; filename: string; sha256: string; size_bytes: number; media_type: string; created_at: string }
export type ArtifactRecord = Artifact & { task_id: string; task_goal: string }
export type LocalSettings = { ollama_model: string; ollama_timeout_seconds: number; task_timeout_seconds: number; approved_workspace_count: number; network_access_enabled: boolean }

async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch(`/api/v1${path}`, { method, headers: { 'Content-Type': 'application/json', 'X-Nexus-Intent': 'local' }, body: body === undefined ? undefined : JSON.stringify(body) })
  if (!response.ok) {
    const error: { detail?: string | { msg: string }[]; message?: string } = await response.json()
    const detail = Array.isArray(error.detail) ? error.detail.map(item => item.msg).join(', ') : error.detail
    throw new Error(detail || error.message || `Request failed (${response.status})`)
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
  updateSettings: (changes: Pick<LocalSettings, 'ollama_model' | 'ollama_timeout_seconds' | 'task_timeout_seconds'>) => request<LocalSettings>('/settings', 'PATCH', changes),
  editPlan: (task: Task, steps: Step[]) => request<Task>(`/tasks/${task.id}/steps`, 'PATCH', { plan_version: task.plan_version, steps: steps.map(({ description, tool_name, args, dependencies }) => ({ description, tool_name, args, dependencies })) }),
  startTask: (id: string) => request<Task>(`/tasks/${id}/start`, 'POST'),
  cancelTask: (id: string) => request<Task>(`/tasks/${id}/cancel`, 'POST'),
  pauseTask: (id: string) => request<Task>(`/tasks/${id}/pause`, 'POST'),
  resumeTask: (id: string) => request<Task>(`/tasks/${id}/resume`, 'POST'),
  approvals: () => request<Approval[]>('/approvals'),
  decide: (approval: Approval, decision: 'approved' | 'rejected') => request<Approval>(`/approvals/${approval.id}/decision`, 'POST', { decision, scope_hash: approval.scope_hash }),
  journal: (id: string) => request<JournalEvent[]>(`/tasks/${id}/journal`),
  artifacts: (id: string) => request<Artifact[]>(`/tasks/${id}/artifacts`),
  artifactLibrary: (offset = 0) => request<{ items: ArtifactRecord[]; total: number }>(`/artifacts?offset=${offset}`),
}
