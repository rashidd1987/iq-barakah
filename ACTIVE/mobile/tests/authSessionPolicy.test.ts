import { shouldClearTokenAfterSessionFailure } from '../src/utils/authSessionPolicy'

function assertEqual(actual: unknown, expected: unknown, label: string) {
  if (actual !== expected) throw new Error(`${label}: expected ${expected}, got ${actual}`)
}

assertEqual(shouldClearTokenAfterSessionFailure({ status: 401 }), true, '401 clears token')
assertEqual(shouldClearTokenAfterSessionFailure({ status: 403 }), true, '403 clears token')
assertEqual(shouldClearTokenAfterSessionFailure({ status: 500 }), false, '5xx preserves token')
assertEqual(shouldClearTokenAfterSessionFailure(new TypeError('network failed')), false, 'network preserves token')
assertEqual(shouldClearTokenAfterSessionFailure(new Error('timeout')), false, 'timeout preserves token')

console.log('auth session policy: 5 passed, 0 failed')
