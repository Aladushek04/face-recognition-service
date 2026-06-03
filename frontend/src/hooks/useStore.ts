import { create } from 'zustand'
import type { UploadResponse, Actor, HealthStatus } from '../types'

interface AppState {
  // Upload state
  uploadResults: UploadResponse[]
  isUploading: boolean
  uploadError: string | null

  // Actors state
  actors: Actor[]
  totalActors: number
  currentPage: number
  searchQuery: string

  // Health state
  health: HealthStatus | null

  // Actions
  setUploadResults: (results: UploadResponse[]) => void
  setUploading: (uploading: boolean) => void
  setUploadError: (error: string | null) => void

  setActors: (actors: Actor[]) => void
  setTotalActors: (total: number) => void
  setCurrentPage: (page: number) => void
  setSearchQuery: (query: string) => void

  setHealth: (health: HealthStatus | null) => void

  clearResults: () => void
}

export const useAppStore = create<AppState>((set) => ({
  // Initial state
  uploadResults: [],
  isUploading: false,
  uploadError: null,

  actors: [],
  totalActors: 0,
  currentPage: 1,
  searchQuery: '',

  health: null,

  // Actions
  setUploadResults: (results) => set({ uploadResults: results }),
  setUploading: (uploading) => set({ isUploading: uploading }),
  setUploadError: (error) => set({ uploadError: error }),

  setActors: (actors) => set({ actors }),
  setTotalActors: (total) => set({ totalActors: total }),
  setCurrentPage: (page) => set({ currentPage: page }),
  setSearchQuery: (query) => set({ searchQuery: query }),

  setHealth: (health) => set({ health }),

  clearResults: () => set({
    uploadResults: [],
    uploadError: null,
  }),
}))
