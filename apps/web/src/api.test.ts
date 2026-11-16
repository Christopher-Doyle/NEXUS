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

test('validation errors identify the field and server failures keep a reference', async () => {
  const fetchMock = vi.fn()
    .mockResolvedValueOnce({ ok: false, status: 422, json: async () => ({ message: 'Invalid input', fields: [{ field: 'body.network_access', message: 'Input should be a valid boolean' }] }) })
    .mockResolvedValueOnce({ ok: false, status: 500, json: async () => ({ message: 'Request failed', correlation_id: 'local-reference' }) })
  vi.stubGlobal('fetch', fetchMock)
  await expect(api.settings()).rejects.toThrow('body.network_access: Input should be a valid boolean')
  await expect(api.settings()).rejects.toThrow('Request failed (reference local-reference)')
})

test('task deletion confirms the exact ID and accepts an empty response', async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 204 })
  vi.stubGlobal('fetch', fetchMock)
  await expect(api.deleteTask('task-1')).resolves.toBeUndefined()
  expect(fetchMock).toHaveBeenCalledWith('/api/v1/tasks/task-1', expect.objectContaining({ method: 'DELETE', body: JSON.stringify({ confirm_id: 'task-1' }) }))
})

test('task journal follows the cursor after a full page', async () => {
  const first = Array.from({ length: 500 }, (_, index) => ({ id: index + 1, type: 'update', occurred_at: '', payload: {} }))
  const fetchMock = vi.fn().mockResolvedValueOnce({ ok: true, json: async () => first }).mockResolvedValueOnce({ ok: true, json: async () => [{ id: 501, type: 'done', occurred_at: '', payload: {} }] })
  vi.stubGlobal('fetch', fetchMock)
  const events = await api.journal('task-1')
  expect(events).toHaveLength(501)
  expect(fetchMock.mock.calls.map(call => call[0])).toEqual(['/api/v1/tasks/task-1/journal?after=0', '/api/v1/tasks/task-1/journal?after=500'])
})
