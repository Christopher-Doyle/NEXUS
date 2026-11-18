import { expect, test } from 'vitest'
import { reportDiff } from './reportDiff'

test('report comparison identifies an inserted and replaced line', () => {
  expect(reportDiff('Heading\nOld evidence\nEnd', 'Heading\nNew evidence\nAdded note\nEnd')).toEqual([
    { kind: 'context', text: 'Heading' },
    { kind: 'removed', text: 'Old evidence' },
    { kind: 'added', text: 'New evidence' },
    { kind: 'added', text: 'Added note' },
    { kind: 'context', text: 'End' },
  ])
})

test('report comparison bounds long documents', () => {
  expect(reportDiff(Array(201).fill('line').join('\n'), 'short')).toBeNull()
})
