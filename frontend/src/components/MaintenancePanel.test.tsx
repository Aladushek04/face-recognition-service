import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { MaintenancePanel } from './MaintenancePanel'
import * as api from '../lib/api'

// Mock the API calls
vi.mock('../lib/api', () => ({
  getToolJobs: vi.fn().mockResolvedValue({ jobs: [], job_types: {} }),
  getSystemStatus: vi.fn().mockResolvedValue({ 
    status: 'ok', 
    checks: [], 
    counts: { actors: 0, actor_images: 0, faiss_vectors: 0, model_files: 0 }, 
    paths: {} 
  }),
  getToolJobLogs: vi.fn().mockResolvedValue(''),
  startToolJob: vi.fn().mockResolvedValue({ 
    status: 'started', 
    job: { id: 'test-job', status: 'queued', type: 'cleanup_actors' } 
  }),
  cancelToolJob: vi.fn().mockResolvedValue({ status: 'cancelled' }),
  getApiBaseUrl: vi.fn().mockReturnValue('/api')
}))

// Mock UI Preferences so we have predictable labels
vi.mock('../lib/useUiPreferences', () => ({
  useUiPreferences: () => ({ language: 'en' })
}))

describe('MaintenancePanel Safety Controls', () => {
  beforeEach(() => {
    vi.stubGlobal('confirm', vi.fn())
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('prevents starting destructive jobs when cancel is clicked in confirm dialog', async () => {
    // Mock user clicking "Cancel" on the confirm dialog
    vi.mocked(window.confirm).mockReturnValue(false)

    render(<MaintenancePanel />)

    // Wait for the panel to load
    await waitFor(() => {
      expect(screen.getByText('Maintenance Center')).toBeInTheDocument()
    })

    // Find the "Cleanup Actors" task which is marked as dangerous
    const cleanupActorsTitle = screen.getByText('Cleanup Actors')
    const cleanupActorsCard = cleanupActorsTitle.closest('section')
    expect(cleanupActorsCard).toBeInTheDocument()

    // Find the "Apply" button within this card
    const applyButton = within(cleanupActorsCard!).getByRole('button', { name: /Apply/i })
    
    // Click it
    fireEvent.click(applyButton)

    // Verify confirm was called
    expect(window.confirm).toHaveBeenCalled()

    // Verify startToolJob was NOT called because we cancelled
    expect(api.startToolJob).not.toHaveBeenCalled()
  })

  it('starts destructive jobs when OK is clicked in confirm dialog', async () => {
    // Mock user clicking "OK" on the confirm dialog
    vi.mocked(window.confirm).mockReturnValue(true)

    render(<MaintenancePanel />)

    // Wait for the panel to load
    await waitFor(() => {
      expect(screen.getByText('Maintenance Center')).toBeInTheDocument()
    })

    const cleanupActorsTitle = screen.getByText('Cleanup Actors')
    const cleanupActorsCard = cleanupActorsTitle.closest('section')
    const applyButton = within(cleanupActorsCard!).getByRole('button', { name: /Apply/i })
    
    // Click it
    fireEvent.click(applyButton)

    // Verify confirm was called
    expect(window.confirm).toHaveBeenCalled()

    // Verify startToolJob WAS called because we confirmed
    expect(api.startToolJob).toHaveBeenCalledWith('cleanup_actors', expect.objectContaining({ apply: true }))
  })
})
