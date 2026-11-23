// The Node modules the plain tests use, as far as they use them: no @types/node needed to type them.
declare module 'node:test' {
  export const test: (name: string, body: () => void | Promise<void>) => void
}
interface ImportMeta {
  readonly url: string
}
declare module 'node:fs' {
  export const readFileSync: (path: URL, encoding: 'utf-8') => string
}
declare module 'node:assert/strict' {
  const assert: {
    ok(value: unknown, message?: string): asserts value
    equal<T>(actual: unknown, expected: T, message?: string): asserts actual is T
    notEqual(actual: unknown, expected: unknown, message?: string): void
    deepEqual(actual: unknown, expected: unknown, message?: string): void
    doesNotMatch(value: string, pattern: RegExp): void
  }
  export default assert
}
