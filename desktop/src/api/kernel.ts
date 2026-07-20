import { api } from './client'

export type KernelId = 'cc-haha' | 'jiuwen-agent-core'

export type KernelInfo = {
  kernel: KernelId
  configDir?: string
  effectiveConfigDir: string
  defaultConfigDir: string
  kernelFile: string
  launchCommand: string
  availableKernels: readonly KernelId[]
}

export const kernelApi = {
  get() {
    return api.get<KernelInfo>('/api/kernel')
  },

  update(update: { kernel?: KernelId; configDir?: string }) {
    return api.put<{ ok: true } & KernelInfo>('/api/kernel', update)
  },
}
