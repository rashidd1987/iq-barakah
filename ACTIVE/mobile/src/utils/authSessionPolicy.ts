export type SessionFailureKind = 'invalid' | 'transient'

export function classifySessionFailure(error: unknown): SessionFailureKind {
  const status = typeof error === 'object' && error !== null && 'status' in error
    ? (error as { status?: unknown }).status
    : undefined
  return status === 401 || status === 403
    ? 'invalid'
    : 'transient'
}

export function shouldClearTokenAfterSessionFailure(error: unknown): boolean {
  return classifySessionFailure(error) === 'invalid'
}
