import { expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import RoomArt from '../RoomArt.vue'

it('uses a category-matched photo and falls back to its illustration when that file fails', async () => {
  const wrapper = mount(RoomArt, { props: { image: 'art:group-0', category: 'studyroom', seed: 42 } })
  const photoUrl = wrapper.get('img').attributes('src')

  expect(photoUrl).toMatch(/^\/photos\/studyroom\/studyroom-\d{2}\.webp$/)
  expect(wrapper.get('.art__note').text()).toBe('분위기 참고')

  await wrapper.get('img').trigger('error')

  expect(wrapper.get('img').attributes('src')).not.toBe(photoUrl)
  expect(wrapper.get('img').attributes('src')).toContain('venue-studyroom')
  expect(wrapper.find('.art__note').exists()).toBe(false)
})
