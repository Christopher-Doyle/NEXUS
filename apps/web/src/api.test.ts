import { afterEach, expect, test, vi } from 'vitest'
import { api } from './api'

afterEach(() => vi.unstubAllGlobals())

test('task creation sends the explicit local intent header', async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ id: 'task-1' }) })
  vi.stubGlobal('fetch', fetchMock)
  await api.createTask({ goal: 'Read the supplied notes', constraints: [], success_criteria: null, capabilities: ['read_file', 'write_report'], network_access: false, workspace_path: null, input_files: [] })
  expect(fetchMock).toHaveBeenCalledWith('/api/v1/tasks', expect.objectContaining({ method: 'POST', headers: expect.objectContaining({ 'X-Nexus-Intent': 'local' }) }))
})

test('API errors reach the task composer', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 403, json: async () => ({ message: 'Folder is not approved' }) }))
  await expect(api.createTask({ goal: 'Read private notes', constraints: [], success_criteria: null, capabilities: ['read_file'], network_access: false, workspace_path: 'C:/Private', input_files: [] })).rejects.toThrow('Folder is not approved')
})
