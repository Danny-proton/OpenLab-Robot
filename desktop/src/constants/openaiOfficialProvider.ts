import type { ModelInfo } from '../types/settings'

export const CLAUDE_OFFICIAL_PROVIDER_ID = 'claude-official'
export const OPENAI_OFFICIAL_PROVIDER_ID = 'openai-official'
// Openlab Robot: 内置官方供应商入口已停用，仅保留用户自定义（custom）大模型。
// 常量保留为空数组以保持类型兼容；如需恢复，改回原来的三个官方 provider id。
export const BUILT_IN_PROVIDER_IDS: readonly string[] = []
export const OPENAI_OFFICIAL_DEFAULT_MODEL_ID = 'gpt-5.6-sol'
export const OPENAI_OFFICIAL_PROVIDER_NAME = 'ChatGPT Official'

// Openlab Robot: 不内置默认模型，用户需在「设置 → 大模型」中配置 custom 模型
export const OPENAI_OFFICIAL_MODELS: ModelInfo[] = []
