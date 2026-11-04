<script setup>
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { toast } from 'vue-sonner'
import { Check } from '@lucide/vue'
import SplitLayout from '@/components/layout/SplitLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import UiAccordion from '@/components/ui/UiAccordion.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import UiTabs from '@/components/ui/UiTabs.vue'
import RoomArt from '@/components/domain/RoomArt.vue'
import { checkEmail, login, signup } from '@/api/authApi'
import { getMe } from '@/api/usersApi'
import { useAuth } from '@/composables/useAuth'
import { useEventLogger } from '@/composables/useEventLogger'

const route = useRoute()
const router = useRouter()
const { setSession } = useAuth()
const { log } = useEventLogger()

const tab = ref(route.query.tab === 'signup' ? 'signup' : 'login')
watch(tab, (t) => router.replace({ query: { ...route.query, tab: t === 'signup' ? 'signup' : undefined } }))
watch(
  () => route.query.tab,
  (t) => (tab.value = t === 'signup' ? 'signup' : 'login'),
)
const tabs = [
  { value: 'login', label: '로그인' },
  { value: 'signup', label: '회원가입' },
]
// next는 우리 화면 경로만 받는다 (바깥 주소로 튕기지 않게)
const next = computed(() => {
  const n = String(route.query.next ?? '')
  return n.startsWith('/') && !n.startsWith('//') ? n : '/'
})

async function focusFirstError() {
  await nextTick()
  document.querySelector('[aria-invalid="true"]')?.focus()
}
async function done(res, message) {
  const user = await getMe(res.access_token)
  setSession(res.access_token, user)
  toast.success(message)
  router.replace(next.value)
}

// 로그인
const lf = reactive({ email: '', password: '' })
const le = reactive({})
const logging = ref(false)
const loginError = ref('')
;['email', 'password'].forEach((k) => watch(() => lf[k], () => delete le[k]))
async function submitLogin() {
  if (logging.value) return
  loginError.value = ''
  if (!lf.email.includes('@')) le.email = '이메일 주소를 적어 주세요.'
  if (!lf.password) le.password = '비밀번호를 적어 주세요.'
  if (Object.keys(le).length) return focusFirstError()
  logging.value = true
  try {
    const res = await login(lf)
    await done(res, '로그인했어요. 하던 일을 이어가세요.')
    log('login')
  } catch (e) {
    lf.password = ''
    loginError.value = e.message
    focusFirstError()
  } finally {
    logging.value = false
  }
}

// 회원가입
const sf = reactive({ name: '', email: '', password: '', password2: '', phone: '', birth: '', gender_digit: '' })
const se = reactive({})
const emailState = ref('') // '' | checking | ok | taken
const terms = reactive({ service: false, privacy: false, marketing: false })
const signing = ref(false)
;['name', 'password', 'password2', 'phone', 'birth', 'gender_digit'].forEach((k) => watch(() => sf[k], () => delete se[k]))
watch(
  () => sf.email,
  () => {
    delete se.email
    emailState.value = ''
  },
)
watch(terms, () => delete se.terms)

const pwChecks = computed(() => [
  { ok: sf.password.length >= 8, label: '8자 이상' },
  { ok: new TextEncoder().encode(sf.password).length <= 72, label: '72바이트 이하' },
])
const allTerms = computed({
  get: () => terms.service && terms.privacy,
  set: (v) => Object.assign(terms, { service: v, privacy: v }),
})
const genderOptions = [
  { value: '1', label: '1900년대 출생 · 남성' },
  { value: '2', label: '1900년대 출생 · 여성' },
  { value: '3', label: '2000년대 출생 · 남성' },
  { value: '4', label: '2000년대 출생 · 여성' },
]
const termItems = [
  { value: 'service', title: '시연용 이용약관 전문 보기', body: '이 약관은 공간큐브 프로젝트의 모의 예약 서비스에 적용됩니다. 실제 결제나 공간 이용 계약은 발생하지 않습니다. 만 14세 이상만 가입할 수 있습니다. 공간은 1시간 단위로 최소 이용시간부터 최대 4시간까지 예약합니다. 결제 버튼을 누르면 모의 결제와 예약을 함께 처리하며 먼저 결제를 마친 예약이 확정됩니다. 이용 시작 전까지 예약을 취소할 수 있고 모의 결제 금액은 전액 환불 처리됩니다. 지난 시간의 예약은 이용 완료로 저장됩니다. 후기는 이용 완료한 본인 예약에 한 번, 이용일과 예약한 날 중 늦은 날부터 7일 안에 작성할 수 있습니다. 탈퇴 시 개인정보는 즉시 지워지고 예약·결제·후기는 회원 번호로 남습니다. 이 내용은 프로젝트 시연용 안내이며 실제 서비스 운영 약관은 별도로 확정해야 합니다.' },
  { value: 'privacy', title: '시연용 개인정보 수집·이용 전문 보기', body: '이 내용은 공간큐브 프로젝트의 모의 서비스에 대한 동의 안내입니다. 회원 식별·로그인과 예약 확인을 위해 이름, 이메일, 비밀번호, 휴대폰 번호를 받고, 생년월일 6자리와 성별 구분 숫자 1자리는 만 14세 이상 가입 자격 확인에 사용합니다. 주민등록번호 전체는 수집하지 않습니다. 필수 항목의 수집·이용 동의를 거부할 수 있으나 회원가입은 할 수 없습니다. 탈퇴하면 이름·연락처·생년월일·이메일 등 개인정보를 즉시 지우고 비밀번호를 무작위 값으로 대체합니다. 예약·결제·후기는 회원 번호로 남으며 공개 후기 작성자는 ‘탈퇴한 회원’으로 표시됩니다. 선택한 새 공간 소식 수신 동의는 거절해도 가입·예약에 영향이 없습니다. 실제 서비스의 운영자·문의처·처리방침은 서비스 운영 전 별도로 확정해야 합니다.' },
]

async function verifyEmail() {
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(sf.email)) {
    se.email = '이메일 주소 형식을 확인해 주세요.'
    return false
  }
  emailState.value = 'checking'
  delete se.email
  const checkedEmail = sf.email
  try {
    const { available } = await checkEmail(checkedEmail)
    if (checkedEmail !== sf.email) return false
    emailState.value = available ? 'ok' : 'taken'
    if (!available) se.email = '이미 가입한 이메일이에요. 로그인 탭에서 들어와 주세요.'
    return available
  } catch (e) {
    emailState.value = ''
    se.email = e.message
    return false
  }
}

async function submitSignup() {
  if (signing.value) return
  if (!sf.name.trim()) se.name = '이름을 적어 주세요.'
  if (emailState.value !== 'ok' && !se.email) await verifyEmail()
  if (!pwChecks.value.every((c) => c.ok)) se.password = '비밀번호는 8자 이상, 72바이트 이하로 적어 주세요.'
  if (sf.password2 !== sf.password) se.password2 = '비밀번호가 서로 달라요.'
  if (!/^01[016789]-?\d{3,4}-?\d{4}$/.test(sf.phone.trim())) se.phone = '휴대폰 번호를 010-1234-5678 형식으로 적어 주세요.'
  if (!/^\d{6}$/.test(sf.birth)) se.birth = '생년월일을 숫자 6자리로 적어 주세요.'
  if (!/^[1-4]$/.test(sf.gender_digit)) se.gender_digit = '성별 구분 숫자 1~4 중 한 자리를 적어 주세요.'
  if (!terms.service || !terms.privacy) se.terms = '필수 약관 두 개에 동의해 주세요.'
  if (Object.keys(se).length) return focusFirstError()
  signing.value = true
  try {
    const fields = { name: sf.name.trim(), email: sf.email.trim(), password: sf.password, phone: sf.phone.trim(), birth: sf.birth, gender_digit: sf.gender_digit }
    const res = await signup({ ...fields, terms_agreed: terms.service, privacy_agreed: terms.privacy, marketing_agreed: terms.marketing })
    log('signup', { user_id: res.user_id })
    lf.email = sf.email
    lf.password = ''
    sf.password = ''
    sf.password2 = ''
    tab.value = 'login'
    toast.success('가입을 마쳤어요. 로그인해 주세요.')
  } catch (e) {
    if (e.code === 'VALIDATION' && e.detail?.fields) {
      e.detail.fields.forEach(({ field, reason }) => {
        const key = ['terms_agreed', 'privacy_agreed'].includes(field) ? 'terms' : field
        se[key] = reason === 'under_14' ? '만 14세 이상부터 가입할 수 있어요.' : reason
      })
    } else se.email = e.message
    focusFirstError()
  } finally {
    signing.value = false
  }
}
</script>

<template>
  <div class="container page">
    <SplitLayout ratio="1fr 1fr">
      <template #start>
        <section class="brand" aria-label="공간큐브 소개">
          <div class="brand__art"><RoomArt kind="group" :tone="1" /></div>
          <h1 class="brand__title">필요한 시간만큼만,<br />딱 맞는 공간을</h1>
          <ul class="brand__list">
            <li><Check :size="18" aria-hidden="true" />스터디룸부터 파티룸까지 다섯 가지 유형</li>
            <li><Check :size="18" aria-hidden="true" />1시간 단위로 고르고 결제하면 예약 확정</li>
            <li><Check :size="18" aria-hidden="true" />이용 후 후기로 다음 사람을 도와요</li>
          </ul>
        </section>
      </template>

      <template #end>
        <section class="card">
          <UiTabs v-model="tab" :tabs="tabs" label="로그인 또는 회원가입">
            <template #panel="{ tab: p }">
              <!-- 로그인 -->
              <form v-if="p.value === 'login'" class="form" novalidate @submit.prevent="submitLogin">
                <p v-if="route.query.next" class="notice">로그인하면 하던 일을 이어서 할 수 있어요.</p>
                <p v-if="loginError" class="err" role="alert">{{ loginError }}</p>
                <UiInput v-model="lf.email" label="이메일" type="email" name="email" autocomplete="username" spellcheck="false" autocapitalize="off" :error="le.email" />
                <UiInput v-model="lf.password" label="비밀번호" type="password" name="password" autocomplete="current-password" :error="le.password" />
                <BaseButton type="submit" size="lg" class="wide" :loading="logging">로그인</BaseButton>
                <p class="hint">처음이신가요? <button type="button" class="link" @click="tab = 'signup'">회원가입</button></p>
                <p class="demo">시연용 계정: study@example.com · 비밀번호 아무거나 8자 이상</p>
              </form>

              <!-- 회원가입 -->
              <form v-else class="form" novalidate @submit.prevent="submitSignup">
                <UiInput v-model="sf.name" label="이름" autocomplete="name" :error="se.name" />
                <UiInput
                  v-model="sf.email"
                  label="이메일"
                  type="email"
                  autocomplete="email"
                  spellcheck="false"
                  autocapitalize="off"
                  :error="se.email"
                  :hint="emailState === 'ok' ? '쓸 수 있는 이메일이에요.' : '로그인할 때 써요.'"
                >
                  <template #append>
                    <BaseButton variant="secondary" :loading="emailState === 'checking'" :disabled="!sf.email" @click="verifyEmail">중복 확인</BaseButton>
                  </template>
                </UiInput>
                <div>
                  <UiInput v-model="sf.password" label="비밀번호" type="password" autocomplete="new-password" :error="se.password" />
                  <ul class="pw" aria-label="비밀번호 조건">
                    <li v-for="c in pwChecks" :key="c.label" :class="{ 'is-ok': c.ok }"><Check :size="14" aria-hidden="true" />{{ c.label }}<span class="sr-only">{{ c.ok ? ' 충족' : ' 미충족' }}</span></li>
                  </ul>
                </div>
                <UiInput v-model="sf.password2" label="비밀번호 확인" type="password" autocomplete="new-password" :error="se.password2" />
                <UiInput v-model="sf.phone" label="휴대폰 번호" type="tel" inputmode="numeric" autocomplete="tel" placeholder="010-1234-5678" :error="se.phone" />
                <UiInput v-model="sf.birth" label="생년월일 6자리" inputmode="numeric" maxlength="6" placeholder="990315" hint="만 14세 이상 가입할 수 있어요." :error="se.birth" />
                <div>
                  <UiSelect v-model="sf.gender_digit" label="출생연도·성별 구분" :options="genderOptions" />
                  <p v-if="se.gender_digit" class="err" role="alert">{{ se.gender_digit }}</p>
                </div>

                <fieldset class="terms" :class="{ 'has-error': se.terms }">
                  <legend class="sr-only">약관 동의</legend>
                  <label class="check check--all"><input v-model="allTerms" type="checkbox" />필수 항목 모두 동의</label>
                  <label class="check"><input v-model="terms.service" type="checkbox" :aria-invalid="Boolean(se.terms && !terms.service)" />[필수] 이용약관</label>
                  <label class="check"><input v-model="terms.privacy" type="checkbox" :aria-invalid="Boolean(se.terms && !terms.privacy)" />[필수] 개인정보 수집·이용</label>
                  <label class="check check--optional"><input v-model="terms.marketing" type="checkbox" />[선택] 새 공간 소식 받기</label>
                  <p v-if="se.terms" class="err" role="alert">{{ se.terms }}</p>
                  <UiAccordion :items="termItems" />
                </fieldset>

                <BaseButton type="submit" size="lg" class="wide" :disabled="!terms.service || !terms.privacy" :loading="signing">가입하기</BaseButton>
              </form>
            </template>
          </UiTabs>
        </section>
      </template>
    </SplitLayout>
  </div>
</template>

<style scoped>
.page {
  padding-block: var(--sp-32) var(--sp-64);
}
.brand {
  display: flex;
  flex-direction: column;
  gap: var(--sp-16);
}
.brand__art {
  max-width: 420px;
  border-radius: var(--r-lg);
  overflow: hidden;
}
.brand__title {
  font-size: clamp(1.625rem, 2.6vw, 2.125rem);
  font-weight: 900;
  line-height: 1.35;
}
.brand__list {
  display: flex;
  flex-direction: column;
  gap: var(--sp-8);
  margin: 0;
  padding: 0;
  list-style: none;
  color: var(--c-ink-2);
}
.brand__list li {
  display: flex;
  align-items: center;
  gap: var(--sp-8);
}
.brand__list :deep(svg) {
  color: var(--c-brand);
}
@media (max-width: 767px) {
  .brand__art,
  .brand__list {
    display: none;
  }
}
.card {
  padding: var(--sp-24);
  border: 1px solid var(--c-line);
  border-radius: var(--r-lg);
  background: var(--c-surface);
  box-shadow: var(--shadow-lift);
}
.form {
  display: flex;
  flex-direction: column;
  gap: var(--sp-16);
  padding-top: var(--sp-24);
}
.notice {
  padding: var(--sp-12) var(--sp-16);
  border-radius: var(--r-md);
  background: var(--c-brand-soft);
  color: var(--c-brand-ink);
  font-weight: 700;
}
.wide {
  width: 100%;
}
.hint {
  text-align: center;
  color: var(--c-muted);
}
.link {
  min-height: var(--tap);
  padding: 0 var(--sp-4);
  border: 0;
  background: none;
  color: var(--c-brand-ink);
  font-weight: 700;
  text-decoration: underline;
  cursor: pointer;
}
.demo {
  padding: var(--sp-12);
  border: 1px dashed var(--c-line-strong);
  border-radius: var(--r-md);
  color: var(--c-subtle);
  font-size: var(--fs-13);
  text-align: center;
}
.pw {
  display: flex;
  gap: var(--sp-12);
  margin: 6px 0 0;
  padding: 0;
  list-style: none;
  font-size: var(--fs-13);
  color: var(--c-subtle);
}
.pw li {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  transition: color var(--t-fast);
}
.pw li.is-ok {
  color: var(--c-success);
  font-weight: 700;
}
.terms {
  display: flex;
  flex-direction: column;
  margin: 0;
  padding: var(--sp-12) var(--sp-16);
  border: 1px solid var(--c-line);
  border-radius: var(--r-md);
}
.terms.has-error {
  border-color: var(--c-danger);
}
.check {
  display: flex;
  align-items: center;
  gap: var(--sp-12);
  min-height: var(--tap);
  cursor: pointer;
}
.check input {
  flex: none;
  width: 20px;
  height: 20px;
  accent-color: var(--c-brand);
}
.check--all {
  padding-bottom: var(--sp-8);
  border-bottom: 1px solid var(--c-line);
  font-weight: 800;
}
.check--optional {
  margin-top: var(--sp-8);
  border-top: 1px solid var(--c-line);
}
.err {
  color: var(--c-danger);
  font-size: var(--fs-13);
}
</style>
