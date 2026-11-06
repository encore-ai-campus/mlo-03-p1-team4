const PHOTO_TYPES = ['studyroom', 'studio', 'cafe', 'lectureroom', 'partyroom']

export const VENUE_PHOTOS = Object.freeze(Object.fromEntries(
  PHOTO_TYPES.map((type) => [
    type,
    Object.freeze(Array.from({ length: 8 }, (_, index) => `/photos/${type}/${type}-${String(index + 1).padStart(2, '0')}.webp`)),
  ]),
))

function stableHash(value) {
  let hash = 2166136261
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index)
    hash = Math.imul(hash, 16777619)
  }
  return hash >>> 0
}

/** Pick one category-matched reference photo consistently for a venue/gallery slot. */
export function getVenuePhoto(category, seed) {
  const code = typeof category === 'string' ? category : category?.code
  const photos = VENUE_PHOTOS[code]
  if (!photos || seed === null || seed === undefined || String(seed).trim() === '') return null

  return photos[stableHash(`${code}:${seed}`) % photos.length]
}
