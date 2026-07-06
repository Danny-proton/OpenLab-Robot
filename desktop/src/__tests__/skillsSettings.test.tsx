import { render, screen, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { Settings } from '../pages/Settings'
import { useSettingsStore } from '../stores/settingsStore'
import { SKILL_CENTER_TAB_ID, useTabStore } from '../stores/tabStore'
import { useUIStore } from '../stores/uiStore'

vi.mock('../api/agents', () => ({
  agentsApi: {
    list: vi.fn().mockResolvedValue({ activeAgents: [], allAgents: [] }),
  },
}))

vi.mock('../stores/providerStore', () => ({
  useProviderStore: () => ({
    providers: [],
    activeId: null,
    presets: [],
    isLoading: false,
    isPresetsLoading: false,
    fetchProviders: vi.fn(),
    fetchPresets: vi.fn(),
    deleteProvider: vi.fn(),
    activateProvider: vi.fn(),
    activateOfficial: vi.fn(),
    testProvider: vi.fn(),
    createProvider: vi.fn(),
    updateProvider: vi.fn(),
    testConfig: vi.fn(),
  }),
}))

vi.mock('../pages/AdapterSettings', () => ({
  AdapterSettings: () => <div>Adapter Settings Mock</div>,
}))

vi.mock('../stores/agentStore', () => ({
  useAgentStore: () => ({
    activeAgents: [],
    allAgents: [],
    isLoading: false,
    error: null,
    selectedAgent: null,
    fetchAgents: vi.fn(),
    selectAgent: vi.fn(),
  }),
}))

describe('Settings > Skills compatibility entry', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    useSettingsStore.setState({ locale: 'en' })
    useTabStore.setState(useTabStore.getInitialState(), true)
    useUIStore.setState({
      activeSettingsTab: 'providers',
      pendingSettingsTab: null,
    })
  })

  it('does not keep the removed Skills entry inside Settings navigation', () => {
    render(<Settings />)

    expect(screen.queryByRole('button', { name: 'Skills' })).not.toBeInTheDocument()
  })

  it('normalizes a legacy active Skills settings tab back to General', async () => {
    const fetchOutputStyles = vi.fn().mockResolvedValue(undefined)
    useSettingsStore.setState({ fetchOutputStyles })
    useUIStore.setState({
      activeSettingsTab: 'skills',
      pendingSettingsTab: null,
    })

    render(<Settings />)

    await waitFor(() => {
      expect(useUIStore.getState().activeSettingsTab).toBe('general')
    })
    expect(useTabStore.getState().activeTabId).not.toBe(SKILL_CENTER_TAB_ID)
    expect(fetchOutputStyles).toHaveBeenCalled()
  })

  it('redirects pending legacy skills settings navigation to the Skill Center without persisting it', async () => {
    useUIStore.setState({
      activeSettingsTab: 'providers',
      pendingSettingsTab: 'skills',
    })

    render(<Settings />)

    await waitFor(() => {
      expect(useTabStore.getState().activeTabId).toBe(SKILL_CENTER_TAB_ID)
    })
    expect(useUIStore.getState().pendingSettingsTab).toBeNull()
    expect(useUIStore.getState().activeSettingsTab).toBe('providers')
    expect(localStorage.getItem('cc-haha-active-settings-tab')).not.toBe('skills')
  })
})
