export type Step = { id: string; ordinal: number; description: string; tool_name: 'read_file' | 'write_report'; args: { path?: string; filename?: string }; args_hash: string; risk_level: string; state: string; dependencies: number[] }
export type Task = { id: string; goal: string; constraints: string[]; success_criteria: string | null; capabilities: string[]; network_access: boolean; state: string; plan_version: number; created_at: string; updated_at: string; steps: Step[] }
export type TaskDraft = { goal: string; constraints: string[]; success_criteria: string | null; capabilities: ('read_file' | 'write_report')[]; network_access: boolean }

async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch(`/api/v1${path}`, { method, headers: { 'Content-Type': 'application/json', 'X-Nexus-Intent': 'local' }, body: body === undefined ? undefined : JSON.stringify(body) })
  if (!response.ok) {
    const error: { detail?: string | { msg: string }[]; message?: string } = await response.json()
    const detail = Array.isArray(error.detail) ? error.detail.map(item => item.msg).join(', ') : error.detail
    throw new Error(detail || error.message || `Request failed (${response.status})`)
  }
  return response.json() as Promise<T>
}

export const api = {
  listTasks: () => request<{ items: Task[]; total: number }>('/tasks'),
  getTask: (id: string) => request<Task>(`/tasks/${id}`),
  createTask: (draft: TaskDraft) => request<Task>('/tasks', 'POST', draft),
  planTask: (id: string) => request<Task>(`/tasks/${id}/plan`, 'POST'),
  editPlan: (task: Task, steps: Step[]) => request<Task>(`/tasks/${task.id}/steps`, 'PATCH', { plan_version: task.plan_version, steps: steps.map(({ description, tool_name, args, dependencies }) => ({ description, tool_name, args, dependencies })) }),
}
