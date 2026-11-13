import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from './api'

describe('API client', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('uses the configured API URL for health checks', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'ok' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await expect(api.health()).resolves.toEqual({ status: 'ok' })

    expect(fetchMock).toHaveBeenCalledOnce()
    expect(fetchMock.mock.calls[0][0]).toMatch(/\/health$/)
  })

  it('returns a useful API error when the backend cannot be reached', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    await expect(api.overview()).rejects.toMatchObject({
      name: 'ApiError',
      status: 0,
      message: expect.stringContaining('Unable to reach the API'),
    })
  })

  it('includes the server detail and status for failed HTTP responses', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      json: async () => ({ detail: 'Database unavailable' }),
    }))

    await expect(api.overview()).rejects.toMatchObject({
      name: 'ApiError',
      status: 503,
      message: 'Database unavailable',
    })
  })
})
