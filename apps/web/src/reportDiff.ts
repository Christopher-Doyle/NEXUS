export type DiffLine = { kind: 'context' | 'added' | 'removed'; text: string }

export function reportDiff(before: string, after: string): DiffLine[] | null {
  const left = before.split('\n')
  const right = after.split('\n')
  if (left.length > 200 || right.length > 200) return null
  const lengths = Array.from({ length: left.length + 1 }, () => new Uint16Array(right.length + 1))
  for (let i = left.length - 1; i >= 0; i--) {
    for (let j = right.length - 1; j >= 0; j--) {
      lengths[i][j] = left[i] === right[j] ? lengths[i + 1][j + 1] + 1 : Math.max(lengths[i + 1][j], lengths[i][j + 1])
    }
  }
  const lines: DiffLine[] = []
  let i = 0
  let j = 0
  while (i < left.length || j < right.length) {
    if (i < left.length && j < right.length && left[i] === right[j]) {
      lines.push({ kind: 'context', text: left[i++] })
      j++
    } else if (j < right.length && (i === left.length || lengths[i][j + 1] > lengths[i + 1][j])) {
      lines.push({ kind: 'added', text: right[j++] })
    } else {
      lines.push({ kind: 'removed', text: left[i++] })
    }
  }
  return lines
}
