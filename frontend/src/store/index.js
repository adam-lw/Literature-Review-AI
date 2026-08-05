import { ServerStore } from './ServerStore.js'
import { SessionStore } from './SessionStore.js'

const mode = import.meta.env.VITE_STORAGE_MODE || 'server'

export const store = mode === 'session' ? SessionStore : ServerStore
export const isDemoMode = mode === 'session'
