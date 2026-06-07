import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { getApiBaseUrl, resolveMediaUrl } from './api'

describe('API utilities', () => {
  beforeEach(() => {
    // Reset any global states if needed
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('getApiBaseUrl returns expected base URL', () => {
    const url = getApiBaseUrl()
    expect(url).toBe('/api')
  })

  it('resolveMediaUrl handles absolute URLs', () => {
    expect(resolveMediaUrl('http://example.com/video.mp4')).toBe('http://example.com/video.mp4')
    expect(resolveMediaUrl('https://example.com/image.jpg')).toBe('https://example.com/image.jpg')
  })

  it('resolveMediaUrl resolves relative api URLs', () => {
    const url = resolveMediaUrl('api/test/media')
    expect(url).toBe('/api/test/media')
  })

  it('resolveMediaUrl resolves /api/ URLs', () => {
    const url = resolveMediaUrl('/api/test/media')
    expect(url).toBe('/api/test/media')
  })
})
