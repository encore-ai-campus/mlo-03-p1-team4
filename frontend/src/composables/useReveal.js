import { ref } from 'vue'
import { useIntersectionObserver, usePreferredReducedMotion } from '@vueuse/core'

// 화면에 처음 들어올 때 한 번만 visible = true. 움직임 줄이기 설정이면 처음부터 true.
// 메인 하단 섹션(최근 후기)에만 쓴다. (docs/공간대여_04 효과 규칙)
export function useReveal(options = { threshold: 0.2 }) {
  const target = ref(null)
  const reduced = usePreferredReducedMotion()
  const visible = ref(reduced.value === 'reduce')

  const { stop } = useIntersectionObserver(
    target,
    ([entry]) => {
      if (entry?.isIntersecting) {
        visible.value = true
        stop()
      }
    },
    options,
  )

  return { target, visible }
}
