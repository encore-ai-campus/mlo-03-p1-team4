import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { toast } from 'vue-sonner'
import { useAuth } from './useAuth'
import { dayOffset } from '@/utils/date'

// 결제 전에는 쓰기를 하지 않고, 로그인 후에도 주소의 선택값을 그대로 복원한다.
export function useBooking() {
  const router = useRouter()
  const { requireLogin } = useAuth()
  const booking = ref(false)
  async function book({ venue_id, date, hours, people }) {
    const selected = [...new Set(hours)].sort((a, b) => a - b)
    if (!Number.isInteger(Number(venue_id)) || !selected.length || selected.length > 4 || !selected.every((h, i) => Number.isInteger(h) && h >= 9 && h <= 22 && (!i || h === selected[i - 1] + 1)) || !Number.isInteger(Number(people)) || Number(people) < 1 || !Number.isFinite(dayOffset(date)) || Math.abs(dayOffset(date)) > 365) {
      toast.error('날짜·시간·인원을 다시 확인해 주세요.')
      return
    }
    const target = { name: 'reserve', query: { venue: venue_id, date, start: selected[0], hours: selected.length, people } }
    if (!requireLogin(router.resolve(target).fullPath)) return
    booking.value = true
    try { await router.push(target) } finally { booking.value = false }
  }
  return { book, booking }
}
