import type { ModelInfo } from '../types/settings'

export const GROK_OFFICIAL_PROVIDER_ID = 'grok-official'
export const GROK_OFFICIAL_DEFAULT_MODEL_ID = 'grok-4.5'
export const GROK_OFFICIAL_PROVIDER_NAME = 'Grok Official'

// Openlab Robot: 不内置默认模型，用户需在「设置 → 大模型」中配置 custom 模型
export const GROK_OFFICIAL_MODELS: ModelInfo[] = []
