import { describe, expect, it } from 'vitest'
import { getVenuePhoto, VENUE_PHOTOS } from '../venuePhoto'

describe('getVenuePhoto', () => {
  it('provides eight reference photos for each supported venue category', () => {
    expect(Object.values(VENUE_PHOTOS).map((photos) => photos.length)).toEqual([8, 8, 8, 8, 8])
  })

  it('returns a stable image for the same category and venue seed', () => {
    expect(getVenuePhoto('studyroom', 42)).toBe(getVenuePhoto('studyroom', 42))
  })

  it('varies the selection across venue ids', () => {
    const photos = new Set(Array.from({ length: 16 }, (_, venueId) => getVenuePhoto('cafe', venueId)))
    expect(photos.size).toBeGreaterThan(1)
  })

  it('only returns an image from the requested category pool', () => {
    const photo = getVenuePhoto('cafe', 'venue-7')
    expect(VENUE_PHOTOS.cafe).toContain(photo)
    expect(photo).toMatch(/^\/photos\/cafe\/cafe-\d{2}\.webp$/)
  })

  it('returns null when category or seed is missing', () => {
    expect(getVenuePhoto('unknown', 'venue-7')).toBeNull()
    expect(getVenuePhoto('cafe', '')).toBeNull()
  })
})
