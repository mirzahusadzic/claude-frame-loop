// The band's files import each other without an extension, as the host loads them; Node's own
// loader asks for one. This finds `./x` as `./x.ts`, for the plain tests alone.
import { registerHooks } from 'node:module'

registerHooks({
  resolve: (specifier, context, next) =>
    specifier.startsWith('.') && !/\.[a-z]+$/.test(specifier) ? next(`${specifier}.ts`, context) : next(specifier, context),
})
