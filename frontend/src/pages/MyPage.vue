<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { toast } from 'vue-sonner'
import { CalendarDays, LogOut, Menu, MessageSquareText, Star, UserRound } from '@lucide/vue'
import SidebarLayout from '@/components/layout/SidebarLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import UiDialog from '@/components/ui/UiDialog.vue'
import UiDrawer from '@/components/ui/UiDrawer.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiSkeleton from '@/components/ui/UiSkeleton.vue'
import UiTabs from '@/components/ui/UiTabs.vue'
import UiPagination from '@/components/ui/UiPagination.vue'
import RoomArt from '@/components/domain/RoomArt.vue'
import ReviewCard from '@/components/domain/ReviewCard.vue'
import { cancelReservation, getMyReservations } from '@/api/reservationsApi'
import { createReview, deleteReview, getMyReviews, updateReview } from '@/api/reviewsApi'
import { changePassword, getMe, updateMe, withdraw } from '@/api/usersApi'
import { useAuth } from '@/composables/useAuth'
import { useEventLogger } from '@/composables/useEventLogger'
import { addDays, dateLabel, hourLabel, todayISO, won } from '@/utils/date'

const route = useRoute()
const router = useRouter()
const { user, token, setSession, logout } = useAuth()
const { log } = useEventLogger()
const section = computed(() => ['reviews', 'account'].includes(route.query.section) ? route.query.section : 'reservations')
const STATUS = { confirmed: { label: '예약 확정', cls: 'ok' }, completed: { label: '이용 완료', cls: 'done' }, cancelled: { label: '취소됨', cls: 'off' } }
const tab = ref(['confirmed', 'completed', 'cancelled'].includes(route.query.tab) ? route.query.tab : route.query.tab === 'done' ? 'completed' : 'confirmed')
const list = ref(null)
const listError = ref('')
const page = ref(1)
const result = ref(null)
const mine = ref(null)
const minePage = ref(1)
const mineError = ref('')
const menuOpen = ref(false)
const tabs = [{ value: 'confirmed', label: '이용 예정' }, { value: 'completed', label: '이용 완료' }, { value: 'cancelled', label: '취소' }]
const menu = computed(() => [
  { icon: CalendarDays, label: '예약 내역', to: '/me', current: section.value === 'reservations' },
  { icon: MessageSquareText, label: '내가 쓴 후기', to: '/me?section=reviews', current: section.value === 'reviews' },
  { icon: UserRound, label: '회원 정보', to: '/me?section=account', current: section.value === 'account' },
])
function doLogout() {
  menuOpen.value = false
  logout()
  toast('로그아웃했어요')
  router.push('/')
}
const timeRange = (r) => `${hourLabel(r.start_hour)}–${hourLabel(r.end_hour)}`
const reviewDeadline = (r) => addDays([r.date, r.created_at.slice(0, 10)].sort().at(-1), 7)
const canReview = (r) => r.status === 'completed' && !r.review_id && todayISO() <= reviewDeadline(r)
let request = 0
async function load() {
  const current = ++request
  list.value = null
  listError.value = ''
  try {
    const data = await getMyReservations(token.value, { status: tab.value, page: page.value, size: 20 })
    if (current !== request) return
    result.value = data
    list.value = data.items
    const target = list.value.find((r) => String(r.reservation_id) === route.query.review)
    if (target && canReview(target)) askReview(target)
  } catch (e) { if (current === request) listError.value = e.message }
}
async function loadReviews() {
  mine.value = null
  mineError.value = ''
  try { mine.value = await getMyReviews(token.value, { page: minePage.value, size: 20 }) }
  catch (e) { mineError.value = e.message }
}
watch(tab, (value) => { page.value = 1; router.replace({ query: { ...route.query, tab: value, review: undefined } }); load() })
watch(page, load)
watch(minePage, loadReviews)
watch(() => route.query.tab, (value) => { if (STATUS[value]) tab.value = value })
watch(section, (value) => { if (value === 'reviews') loadReviews() }, { immediate: true })

const cancelTarget = ref(null)
const cancelOpen = ref(false)
const cancelling = ref(false)
const keepButton = ref(null)
function askCancel(r) { cancelTarget.value = r; cancelOpen.value = true }
function focusKeep(event) { event.preventDefault(); keepButton.value?.focus() }
async function doCancel() {
  if (cancelling.value) return
  cancelling.value = true
  try {
    await cancelReservation(cancelTarget.value.reservation_id, token.value)
    log('reservation_cancel_attempt', { venue_id: cancelTarget.value.venue_id, reservation_id: cancelTarget.value.reservation_id })
    toast.success('예약을 취소했어요. 결제 금액은 전액 모의 환불됐어요.')
    cancelOpen.value = false
    await load()
  } catch (e) { toast.error(e.message) } finally { cancelling.value = false }
}
const reviewTarget = ref(null)
const reviewOpen = ref(false)
const review = reactive({ rating: 0, content: '', error: '' })
const posting = ref(false)
const RATING_LABEL = ['', '별로예요', '아쉬워요', '괜찮아요', '좋아요', '최고예요']
function askReview(r) {
  editTarget.value = null
  reviewTarget.value = r
  Object.assign(review, { rating: 0, content: '', error: '' })
  reviewOpen.value = true
}
async function postReview() {
  if (posting.value) return
  if (!review.rating) return (review.error = '별점을 골라 주세요.')
  if (!review.content.trim()) return (review.error = '후기 내용을 적어 주세요.')
  posting.value = true
  try {
    await createReview(reviewTarget.value.reservation_id, { rating: review.rating, content: review.content.trim() }, token.value)
    log('review_create', { venue_id: reviewTarget.value.venue_id, reservation_id: reviewTarget.value.reservation_id, rating: review.rating })
    toast.success('후기를 올렸어요.')
    reviewOpen.value = false
    await router.replace({ query: { ...route.query, review: undefined } })
    await load()
  } catch (e) { review.error = e.message } finally { posting.value = false }
}
watch(() => [review.rating, review.content], () => (review.error = ''))
// 내가 쓴 후기 수정·삭제(F-50). 수정은 후기 쓰기 창을 같이 쓴다.
const editTarget = ref(null)
function askEdit(item) {
  editTarget.value = item
  reviewTarget.value = null
  Object.assign(review, { rating: item.rating, content: item.content, error: '' })
  reviewOpen.value = true
}
async function saveEdit() {
  if (posting.value) return
  if (!review.content.trim()) return (review.error = '후기 내용을 적어 주세요.')
  const body = {}
  if (review.rating !== editTarget.value.rating) body.rating = review.rating
  if (review.content.trim() !== editTarget.value.content) body.content = review.content.trim()
  if (!Object.keys(body).length) { reviewOpen.value = false; return }
  posting.value = true
  try {
    await updateReview(editTarget.value.review_id, body, token.value)
    toast.success('후기를 고쳤어요.')
    reviewOpen.value = false
    await loadReviews()
  } catch (e) {
    review.error = e.message
    if (e.code === 'REVIEW_NOT_FOUND') { reviewOpen.value = false; toast.error(e.message); await loadReviews() }
  } finally { posting.value = false }
}
function submitReview() { return editTarget.value ? saveEdit() : postReview() }
watch(reviewOpen, (open) => { if (!open) editTarget.value = null })
const deleteTarget = ref(null)
const deleteOpen = ref(false)
const deleting = ref(false)
const keepReviewButton = ref(null)
function askDelete(item) { deleteTarget.value = item; deleteOpen.value = true }
function focusKeepReview(event) { event.preventDefault(); keepReviewButton.value?.focus() }
async function doDelete() {
  if (deleting.value) return
  deleting.value = true
  try {
    await deleteReview(deleteTarget.value.review_id, token.value)
    toast.success('후기를 지웠어요.')
  } catch (e) {
    if (e.code !== 'REVIEW_NOT_FOUND') { toast.error(e.message); return }
  } finally { deleting.value = false }
  deleteOpen.value = false
  await loadReviews()
}

// 회원 정보 수정·비밀번호 변경(F-03)
const PHONE = /^01[016789]-?\d{3,4}-?\d{4}$/
const info = reactive({ name: '', phone: '', marketing_agreed: false })
const infoErr = reactive({})
const savingInfo = ref(false)
function fillInfo(me) { if (me) Object.assign(info, { name: me.name ?? '', phone: me.phone ?? '', marketing_agreed: !!me.marketing_agreed }) }
watch(user, fillInfo, { immediate: true })
const infoChanges = computed(() => {
  if (!user.value) return {}
  const body = {}
  if (info.name.trim() !== user.value.name) body.name = info.name.trim()
  if (info.phone.trim() !== (user.value.phone ?? '')) body.phone = info.phone.trim()
  if (info.marketing_agreed !== !!user.value.marketing_agreed) body.marketing_agreed = info.marketing_agreed
  return body
})
const infoDirty = computed(() => Object.keys(infoChanges.value).length > 0)
;['name', 'phone'].forEach((k) => watch(() => info[k], () => delete infoErr[k]))
function fieldErrors(e, target) {
  if (e.code !== 'VALIDATION' || !e.detail?.fields) return false
  e.detail.fields.forEach(({ field, reason }) => { target[field] = reason })
  return true
}
async function saveInfo() {
  if (savingInfo.value || !infoDirty.value) return
  if (!info.name.trim()) infoErr.name = '이름을 입력해 주세요.'
  if (!PHONE.test(info.phone.trim())) infoErr.phone = '휴대폰 번호를 010-1234-5678 형식으로 적어 주세요.'
  if (infoErr.name || infoErr.phone) return
  savingInfo.value = true
  try {
    const me = await updateMe(infoChanges.value, token.value)
    setSession(token.value, { ...user.value, ...me })
    toast.success('회원 정보를 저장했어요.')
  } catch (e) { if (!fieldErrors(e, infoErr)) toast.error(e.message) } finally { savingInfo.value = false }
}
const pw = reactive({ current: '', next: '', next2: '' })
const pwErr = reactive({})
const savingPw = ref(false)
;['current', 'next', 'next2'].forEach((k) => watch(() => pw[k], () => delete pwErr[k]))
async function savePassword() {
  if (savingPw.value) return
  if (!pw.current) pwErr.current = '현재 비밀번호를 입력해 주세요.'
  if (pw.next.length < 8 || new TextEncoder().encode(pw.next).length > 72) pwErr.next = '8자 이상, 72바이트 이하로 입력해 주세요.'
  else if (pw.next === pw.current) pwErr.next = '지금 비밀번호와 다르게 정해 주세요.'
  if (pw.next2 !== pw.next) pwErr.next2 = '새 비밀번호가 서로 달라요.'
  if (pwErr.current || pwErr.next || pwErr.next2) return
  savingPw.value = true
  try {
    await changePassword({ current_password: pw.current, new_password: pw.next }, token.value)
    Object.assign(pw, { current: '', next: '', next2: '' })
    toast.success('비밀번호를 바꿨어요.')
  } catch (e) {
    if (e.code === 'WRONG_PASSWORD') pwErr.current = e.message
    else if (!fieldErrors(e, pwErr)) toast.error(e.message)
    else if (pwErr.new_password) { pwErr.next = pwErr.new_password; delete pwErr.new_password }
  } finally { savingPw.value = false }
}

// 회원 탈퇴(F-04, 11-05): 취소할 수 있는 예약이 남으면 막고 예약 내역으로 안내한다. 이용 중인 예약은 막지 않는다.
const withdrawOpen = ref(false)
const withdrawing = ref(false)
const futureCount = ref(0)
const withdrawReady = ref(false)
const withdrawError = ref('')
const withdrawConfirmed = ref(false)
async function askWithdraw() {
  withdrawReady.value = false
  withdrawConfirmed.value = false
  withdrawError.value = ''
  futureCount.value = 0
  withdrawOpen.value = true
  try {
    const data = await getMyReservations(token.value, { status: 'confirmed', page: 1, size: 50 })
    futureCount.value = data.items.filter((r) => r.can_cancel).length
    withdrawReady.value = true
  } catch (e) { withdrawError.value = e.message }
}
async function doWithdraw() {
  if (!withdrawReady.value || futureCount.value || !withdrawConfirmed.value || withdrawing.value) return
  withdrawing.value = true
  try {
    await withdraw(token.value)
    logout()
    withdrawOpen.value = false
    toast.success('탈퇴했어요. 개인정보가 삭제됐어요.')
    await router.replace('/')
  } catch (e) {
    if (e.code === 'HAS_UPCOMING_RESERVATION') futureCount.value = e.detail?.count ?? 1
    else withdrawError.value = e.message
  } finally { withdrawing.value = false }
}
function goUpcoming() {
  withdrawOpen.value = false
  router.push({ path: '/me', query: { tab: 'confirmed' } })
}
getMe(token.value).then((me) => setSession(token.value, me)).catch((e) => toast.error(e.message))
load()
</script>

<template>
  <div class="container page">
    <SidebarLayout label="내 메뉴">
      <template #sidebar>
        <div class="profile">
          <span class="profile__avatar" aria-hidden="true">{{ user?.name?.[0] ?? '?' }}</span>
          <div>
            <strong>{{ user?.name }}</strong>
            <span>{{ user?.email }}</span>
          </div>
        </div>
        <nav class="menu" aria-label="내 메뉴">
          <template v-for="m in menu" :key="m.label">
            <RouterLink v-if="m.to" :to="m.to" class="menu__item" :aria-current="m.current ? 'page' : undefined"><component :is="m.icon" :size="20" aria-hidden="true" />{{ m.label }}</RouterLink>
            <span v-else class="menu__item is-soon"><component :is="m.icon" :size="20" aria-hidden="true" />{{ m.label }}<small>준비 중</small></span>
          </template>
          <button type="button" class="menu__item menu__logout" @click="doLogout"><LogOut :size="20" aria-hidden="true" />로그아웃</button>
        </nav>
      </template>

      <template #mobile-trigger>
        <UiDrawer v-model:open="menuOpen" title="내 메뉴" side="left">
          <template #trigger>
            <BaseButton variant="secondary"><Menu :size="18" aria-hidden="true" />내 메뉴</BaseButton>
          </template>
          <nav class="menu" aria-label="내 메뉴">
            <template v-for="m in menu" :key="m.label">
              <RouterLink v-if="m.to" :to="m.to" class="menu__item" :aria-current="m.current ? 'page' : undefined" @click="menuOpen = false"><component :is="m.icon" :size="20" aria-hidden="true" />{{ m.label }}</RouterLink>
              <span v-else class="menu__item is-soon"><component :is="m.icon" :size="20" aria-hidden="true" />{{ m.label }}<small>준비 중</small></span>
            </template>
            <button type="button" class="menu__item menu__logout" @click="doLogout"><LogOut :size="20" aria-hidden="true" />로그아웃</button>
          </nav>
        </UiDrawer>
      </template>

      <h1 class="title">{{ section === 'reviews' ? '내가 쓴 후기' : section === 'account' ? '회원 정보' : '예약 내역' }}</h1>
      <section v-if="section === 'reviews'" aria-label="내 후기">
        <div v-if="mineError" class="empty" role="alert"><p>{{ mineError }}</p><BaseButton variant="secondary" @click="loadReviews">다시 시도</BaseButton></div>
        <UiSkeleton v-else-if="!mine" height="180px" />
        <p v-else-if="!mine.items.length" class="empty">아직 쓴 후기가 없어요. 이용 완료 예약에서 후기를 작성해 보세요.</p>
        <template v-else>
          <ul class="cards">
            <li v-for="item in mine.items" :key="item.review_id" class="own-review">
              <ReviewCard :review="item" show-room />
              <div class="own-review__actions">
                <BaseButton variant="secondary" :aria-label="`${item.venue_name} 후기 고치기`" @click="askEdit(item)">고치기</BaseButton>
                <BaseButton variant="quiet" :aria-label="`${item.venue_name} 후기 지우기`" @click="askDelete(item)">지우기</BaseButton>
              </div>
            </li>
          </ul>
          <UiPagination v-model="minePage" :total="mine.total" :size="20" />
        </template>
      </section>
      <div v-else-if="section === 'account'" class="account-page">
        <section class="account-box" aria-labelledby="info-title">
          <h2 id="info-title" class="account-box__title">기본 정보</h2>
          <form class="review-form" novalidate @submit.prevent="saveInfo">
            <dl class="account"><dt>이메일</dt><dd>{{ user?.email }}</dd></dl>
            <UiInput v-model="info.name" label="이름" autocomplete="name" maxlength="50" :error="infoErr.name" />
            <UiInput v-model="info.phone" label="휴대폰 번호" type="tel" inputmode="numeric" autocomplete="tel" placeholder="010-1234-5678" :error="infoErr.phone" />
            <label class="withdraw-check"><input v-model="info.marketing_agreed" type="checkbox" />새 공간·할인 소식 받기(선택)</label>
            <p class="dialog-note">이메일·생년월일·성별은 바꿀 수 없어요.</p>
            <div><BaseButton type="submit" :disabled="!infoDirty" :loading="savingInfo">회원 정보 저장</BaseButton></div>
          </form>
        </section>
        <section class="account-box" aria-labelledby="pw-title">
          <h2 id="pw-title" class="account-box__title">비밀번호 변경</h2>
          <form class="review-form" novalidate @submit.prevent="savePassword">
            <UiInput v-model="pw.current" label="현재 비밀번호" type="password" autocomplete="current-password" :error="pwErr.current" />
            <UiInput v-model="pw.next" label="새 비밀번호" type="password" autocomplete="new-password" hint="8자 이상" :error="pwErr.next" />
            <UiInput v-model="pw.next2" label="새 비밀번호 확인" type="password" autocomplete="new-password" :error="pwErr.next2" />
            <div><BaseButton type="submit" variant="secondary" :loading="savingPw">비밀번호 변경</BaseButton></div>
          </form>
        </section>
        <section class="account-box" aria-labelledby="leave-title">
          <h2 id="leave-title" class="account-box__title">회원 탈퇴</h2>
          <p class="dialog-note">탈퇴하면 개인정보가 바로 지워져요. 예약과 후기는 회원 번호로 남아요. 이용 예정 예약이 있으면 먼저 취소해야 해요.</p>
          <div><BaseButton variant="secondary" @click="askWithdraw">회원 탈퇴</BaseButton></div>
        </section>
      </div>
      <UiTabs v-else v-model="tab" :tabs="tabs" label="예약 상태">
        <template #panel>
          <div v-if="listError" class="empty" role="alert"><p>{{ listError }}</p><BaseButton variant="secondary" @click="load">다시 시도</BaseButton></div>
          <div v-else-if="!list" class="cards" aria-busy="true"><UiSkeleton v-for="i in 3" :key="i" height="132px" radius="var(--r-lg)" /></div>
          <div v-else-if="!list.length" class="empty"><p>{{ tab === 'confirmed' ? '다가오는 예약이 없어요.' : tab === 'completed' ? '이용을 마친 예약이 없어요.' : '취소한 예약이 없어요.' }}</p><BaseButton to="/search" variant="secondary">공간 둘러보기</BaseButton></div>
          <template v-else>
            <ul class="cards">
              <li v-for="r in list" :key="r.reservation_id" class="res">
                <RouterLink :to="`/venues/${r.venue_id}`" class="res__thumb" tabindex="-1" aria-hidden="true"><RoomArt :image="r.venue.image" :category="r.venue.category" /></RouterLink>
                <div class="res__body">
                  <div class="res__top"><span class="status" :class="`status--${STATUS[r.status].cls}`">{{ STATUS[r.status].label }}</span><span class="res__no num">예약 {{ r.reservation_id }}</span></div>
                  <RouterLink :to="`/venues/${r.venue_id}`" class="res__name">{{ r.venue.name }}</RouterLink>
                  <p class="res__when num">{{ dateLabel(r.date) }} {{ timeRange(r) }} · {{ r.headcount }}명</p>
                  <p class="res__pay num">{{ won(r.total_price) }} · {{ r.payment.status === 'refunded' ? '환불 완료' : '결제 완료' }}</p>
                </div>
                <div class="res__actions">
                  <BaseButton v-if="r.can_cancel" variant="quiet" @click="askCancel(r)">예약 취소</BaseButton>
                  <BaseButton v-if="canReview(r)" variant="secondary" @click="askReview(r)">후기 쓰기</BaseButton>
                  <span v-else-if="r.review_id" class="res__done">후기 작성 완료</span>
                  <span v-else-if="r.status === 'completed'" class="dialog-note">후기 작성 기한이 지났어요</span>
                  <BaseButton v-if="r.status === 'cancelled'" :to="`/venues/${r.venue_id}`" variant="secondary">다시 예약</BaseButton>
                </div>
              </li>
            </ul>
            <UiPagination v-model="page" :total="result.total" :size="20" />
          </template>
        </template>
      </UiTabs>
    </SidebarLayout>

    <UiDialog v-model:open="cancelOpen" title="이 예약을 취소할까요?" :description="cancelTarget ? `${cancelTarget.venue.name} · ${dateLabel(cancelTarget.date)} ${timeRange(cancelTarget)}` : ''" @open-auto-focus="focusKeep">
      <p class="dialog-note">취소하면 칸이 바로 풀려 다른 사람이 예약할 수 있어요. 모의 결제 금액은 전액 환불 처리돼요.</p>
      <template #actions>
        <button ref="keepButton" type="button" class="safe-button" @click="cancelOpen = false">취소하지 않기</button>
        <BaseButton class="danger-button" :loading="cancelling" @click="doCancel">예약 취소</BaseButton>
      </template>
    </UiDialog>

    <UiDialog v-model:open="reviewOpen" :title="editTarget ? '후기 고치기' : '후기 쓰기'" :description="editTarget ? editTarget.venue_name : reviewTarget ? `${reviewTarget.venue.name} · ${reviewDeadline(reviewTarget)}까지 작성 가능` : ''">
      <form id="review-form" class="review-form" novalidate @submit.prevent="submitReview">
        <fieldset class="stars">
          <legend>별점</legend>
          <div class="stars__row">
            <label v-for="n in 5" :key="n" class="star" :class="{ 'is-on': n <= review.rating }">
              <input v-model="review.rating" type="radio" name="rating" :value="n" class="star__input" />
              <Star :size="30" fill="currentColor" aria-hidden="true" /><span class="sr-only">{{ n }}점</span>
            </label>
            <span class="stars__label" aria-live="polite">{{ RATING_LABEL[review.rating] }}</span>
          </div>
        </fieldset>
        <UiInput v-model="review.content" label="어땠나요?" multiline rows="4" maxlength="2000" placeholder="다음 사람에게 도움이 되는 점을 적어 주세요" :hint="`${review.content.length}/2000`" />
        <p v-if="review.error" class="err" role="alert">{{ review.error }}</p>
      </form>
      <template #actions>
        <BaseButton variant="secondary" @click="reviewOpen = false">닫기</BaseButton>
        <BaseButton type="submit" form="review-form" :loading="posting">{{ editTarget ? '고친 후기 저장' : '후기 올리기' }}</BaseButton>
      </template>
    </UiDialog>
    <UiDialog v-model:open="deleteOpen" title="이 후기를 지울까요?" :description="deleteTarget ? deleteTarget.venue_name : ''" @open-auto-focus="focusKeepReview">
      <p class="dialog-note">지운 후기는 되돌릴 수 없고, 같은 예약으로 다시 쓸 수 없어요.</p>
      <template #actions>
        <button ref="keepReviewButton" type="button" class="safe-button" @click="deleteOpen = false">지우지 않기</button>
        <BaseButton class="danger-button" :loading="deleting" @click="doDelete">후기 지우기</BaseButton>
      </template>
    </UiDialog>
    <UiDialog v-model:open="withdrawOpen" title="회원 탈퇴" description="탈퇴하면 되돌릴 수 없어요. 아래 내용을 확인해 주세요.">
      <div class="review-form">
        <p>이름·이메일·연락처·생년월일은 바로 지워지고, 예약·후기는 ‘탈퇴한 회원’으로 남아요.</p>
        <p v-if="!withdrawReady && !withdrawError" role="status">이용 예정 예약을 확인하고 있어요.</p>
        <p v-if="futureCount" class="err" role="alert">이용 예정 예약이 {{ futureCount }}건 있어요. 예약 내역에서 먼저 취소해 주세요.</p>
        <p v-if="withdrawError" class="err" role="alert">{{ withdrawError }}</p>
        <label v-if="!futureCount" class="withdraw-check"><input v-model="withdrawConfirmed" type="checkbox" :disabled="!withdrawReady" />개인정보 삭제와 예약·후기 유지 내용을 확인했어요.</label>
      </div>
      <template #actions>
        <BaseButton variant="secondary" @click="withdrawOpen = false">탈퇴하지 않기</BaseButton>
        <BaseButton v-if="futureCount" @click="goUpcoming">예약 내역 보기</BaseButton>
        <BaseButton v-else class="danger-button" :disabled="!withdrawReady || !withdrawConfirmed" :loading="withdrawing" @click="doWithdraw">탈퇴하기</BaseButton>
      </template>
    </UiDialog>
  </div>
</template>

<style scoped>
.page {
  padding-block: var(--sp-24) var(--sp-64);
}
.profile {
  display: flex;
  align-items: center;
  gap: var(--sp-12);
  padding: var(--sp-16);
  border: 0;
  border-radius: var(--r-lg);
  background: var(--c-surface);
}
.profile > div {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.profile span:not(.profile__avatar) {
  overflow: hidden;
  color: var(--c-subtle);
  font-size: var(--fs-13);
  text-overflow: ellipsis;
}
.profile__avatar {
  display: grid;
  flex: none;
  place-items: center;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: var(--c-brand);
  color: var(--c-on-dark);
  font-size: var(--fs-20);
  font-weight: 800;
}
.menu {
  display: flex;
  flex-direction: column;
  gap: var(--sp-8);
  margin-top: var(--sp-16);
}
.menu__item {
  display: flex;
  align-items: center;
  gap: var(--sp-12);
  min-height: var(--tap);
  padding: 0 var(--sp-12);
  border-radius: var(--r-sm);
  color: var(--c-ink-2);
  font-weight: 500;
  text-decoration: none;
}
a.menu__item:hover,
.menu__logout:hover {
  background: var(--c-brand-soft);
}
.menu__logout {
  width: 100%;
  border: 0;
  background: transparent;
  font: inherit;
  text-align: left;
  cursor: pointer;
}
.menu__item[aria-current='page'] {
  background: var(--c-brand-soft);
  color: var(--c-brand-ink);
  font-weight: 800;
}
.menu__item.is-soon {
  color: var(--c-subtle);
}
.menu__item small {
  margin-left: auto;
  font-size: var(--fs-12);
}
.title {
  margin-top: var(--sp-16);
  margin-bottom: var(--sp-16);
  font-size: clamp(1.5rem, 3vw, 2rem);
  font-weight: 900;
}
.cards {
  display: flex;
  flex-direction: column;
  gap: var(--sp-12);
  margin: var(--sp-16) 0 0;
  padding: 0;
  list-style: none;
}
.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--sp-12);
  margin-top: var(--sp-16);
  padding: var(--sp-48) var(--sp-16);
  border: 1px dashed var(--c-line-strong);
  border-radius: var(--r-lg);
  color: var(--c-muted);
}
.res {
  display: grid;
  grid-template-columns: 96px 1fr;
  gap: var(--sp-16);
  padding: var(--sp-16);
  border: 0;
  border-radius: var(--r-lg);
  background: var(--c-surface);
}
@media (min-width: 768px) {
  .res {
    grid-template-columns: 128px 1fr auto;
    align-items: center;
  }
}
.res__thumb {
  align-self: start;
  border-radius: var(--r-md);
  overflow: hidden;
}
.res__body {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
.res__top {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--sp-8);
}
.status {
  font-size: var(--fs-15);
  font-weight: 800;
}
/* 상태는 알약 대신 색 글자 */
.status--wait,
.status--ok {
  color: var(--c-brand-ink);
}
.status--done {
  color: var(--c-ink-2);
}
.status--off {
  color: var(--c-subtle);
}
.dday {
  color: var(--c-brand-ink);
  font-size: var(--fs-13);
  font-weight: 800;
}
.res__no {
  color: var(--c-subtle);
  font-size: var(--fs-12);
}
.res__name {
  color: var(--c-ink);
  font-size: var(--fs-16);
  font-weight: 800;
  text-decoration: none;
}
.res__name:hover {
  text-decoration: underline;
}
.res__when {
  color: var(--c-ink-2);
}
.res__pay {
  color: var(--c-subtle);
  font-size: var(--fs-13);
}
.res__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-8);
  grid-column: 1 / -1;
}
@media (min-width: 768px) {
  .res__actions {
    grid-column: auto;
    justify-content: flex-end;
  }
}
.res__done {
  display: inline-flex;
  align-items: center;
  min-height: var(--tap);
  color: var(--c-success);
  font-weight: 700;
}
.dialog-note {
  color: var(--c-muted);
}
.review-form {
  display: flex;
  flex-direction: column;
  gap: var(--sp-16);
}
.star { position: relative; }
.star__input { position: absolute; inset: 0; width: 100%; height: 100%; margin: 0; opacity: 0; cursor: pointer; z-index: 1; }
.stars {
  margin: 0;
  padding: 0;
  border: 0;
}
.stars legend {
  margin-bottom: var(--sp-8);
  font-size: var(--fs-13);
  font-weight: 700;
  color: var(--c-muted);
}
.stars__row {
  display: flex;
  align-items: center;
  gap: var(--sp-8);
}
.star {
  display: grid;
  place-items: center;
  width: var(--tap);
  height: var(--tap);
  border-radius: var(--r-sm);
  color: var(--c-line-strong);
  font-size: 32px;
  cursor: pointer;
  transition: transform var(--t-fast), color var(--t-fast);
}
.star.is-on {
  color: var(--c-brand);
}
.star:active {
  transform: scale(0.95);
}
.star:has(:focus-visible) {
  outline: 2px solid var(--c-brand);
}
.stars__label {
  margin-left: var(--sp-8);
  font-weight: 700;
}
.err {
  color: var(--c-danger);
  font-size: var(--fs-13);
}

.safe-button { min-height: var(--tap); padding: 0 var(--sp-16); border: 0; border-radius: var(--r-md); background: var(--c-fill); color: var(--c-ink); font-weight: 700; cursor: pointer; }
.danger-button, .danger-button:hover:not(:disabled) { background: var(--c-danger); color: var(--c-on-dark); }
.own-review { display: flex; flex-direction: column; gap: var(--sp-8); padding-block: var(--sp-16); }
.own-review__actions { display: flex; flex-wrap: wrap; gap: var(--sp-8); }
.account-page { display: flex; flex-direction: column; gap: var(--sp-24); max-width: 560px; }
.account-box { display: flex; flex-direction: column; gap: var(--sp-16); padding: var(--sp-24); border-radius: var(--r-lg); background: var(--c-surface); }
.account-box__title { font-size: var(--fs-18, 1.125rem); font-weight: 800; }
.account { display: grid; grid-template-columns: auto 1fr; gap: var(--sp-12) var(--sp-24); }
.account dd { margin: 0; overflow-wrap: anywhere; }
.withdraw-check { display: flex; align-items: center; min-height: var(--tap); gap: var(--sp-8); }
</style>
