<script setup>
import { computed, ref } from 'vue'
import UiAccordion from '@/components/ui/UiAccordion.vue'
import UiChip from '@/components/ui/UiChip.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiSelect from '@/components/ui/UiSelect.vue'

// 조회 화면 필터. 데스크톱 사이드바(모두 펼침)와 모바일 드로어(첫 묶음만 펼침)에서 같은 내용을 아코디언으로 그린다.
const props = defineProps({
  categories: { type: Array, required: true },
  regions: { type: Array, required: true },
  districts: { type: Array, default: () => [] },
  facilities: { type: Array, required: true },
  compact: { type: Boolean, default: false },
})
const f = defineModel({ type: Object, required: true })

const sidoOptions = computed(() => ['전국', ...props.regions])
const sigunguOptions = computed(() => ['전체', ...props.districts.map((r) => r.sigungu)])
const peopleOptions = ['1', '2', '4', '6', '8', '10', '15'].map((n) => ({ value: n, label: `${n}명 이상` }))
const typeOptions = computed(() => [{ code: 'all', name: '전체' }, ...props.categories])

const set = (patch) => (f.value = { ...f.value, ...patch })
function toggleFacility(name, on) {
  const s = new Set(f.value.facilities)
  if (on) s.add(name)
  else s.delete(name)
  set({ facilities: [...s] })
}
const expanded = ref(false)
const visibleFacilities = computed(() => expanded.value ? props.facilities : props.facilities.slice(0, 6))
const groups = [
  { value: 'type', title: '유형' },
  { value: 'region', title: '지역 · 인원' },
  { value: 'facility', title: '시설' },
]
</script>

<template>
  <div class="filters">
    <UiAccordion :items="groups" :default-open="compact ? ['type'] : ['type', 'region', 'facility']">
      <template #type>
        <div class="chips" role="group" aria-label="유형">
          <button v-for="c in typeOptions" :key="c.code" type="button" class="type" :aria-pressed="f.category === c.code" @click="set({ category: c.code })">
            {{ c.name }}
          </button>
        </div>
      </template>
      <template #region>
        <div class="stack">
          <UiSelect :model-value="f.sido" label="시·도" :options="sidoOptions" @update:model-value="(v) => set({ sido: v, sigungu: '전체' })" />
          <UiSelect v-if="f.sido !== '전국'" :model-value="f.sigungu" label="시·군·구" :options="sigunguOptions" @update:model-value="(v) => set({ sigungu: v })" />
          <UiSelect :model-value="f.people" label="인원" :options="peopleOptions" @update:model-value="(v) => set({ people: v })" />
        </div>
      </template>
      <template #facility>
        <div class="chips">
          <UiChip v-for="item in visibleFacilities" :key="item.facility_id" :model-value="f.facilities.map(String).includes(String(item.facility_id))" @update:model-value="(on) => toggleFacility(String(item.facility_id), on)">{{ item.name }}</UiChip>
        </div>
        <button v-if="facilities.length > 6" type="button" class="more" :aria-expanded="expanded" @click="expanded = !expanded">{{ expanded ? '시설 접기' : '시설 더 보기' }}</button>
      </template>
    </UiAccordion>

    <UiInput :model-value="f.q" label="검색어" type="search" placeholder="공간 이름이나 시설 (예: 호리존…)" autocomplete="off" @update:model-value="(v) => set({ q: v })" />
    <UiChip :model-value="f.now" @update:model-value="(v) => set({ now: v })"><span class="now-dot" aria-hidden="true" />지금 이용 가능한 곳만</UiChip>
  </div>
</template>

<style scoped>
.more { min-height: var(--tap); border: 0; padding: var(--sp-8); color: var(--c-brand-ink); background: transparent; cursor: pointer; }
.filters {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--sp-16);
}
.filters > :first-child,
.filters > .input-field {
  align-self: stretch;
}
.stack {
  display: flex;
  flex-direction: column;
  gap: var(--sp-12);
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-8);
}
.type {
  min-height: var(--tap);
  padding: 0 var(--sp-12);
  border: 1px solid var(--c-line-strong);
  border-radius: 999px;
  background: var(--c-surface);
  font-size: var(--fs-15);
  cursor: pointer;
  transition: border-color var(--t-fast), background-color var(--t-fast);
}
.type:hover {
  border-color: var(--c-brand);
}
.type[aria-pressed='true'] {
  background: var(--c-ink);
  border-color: var(--c-ink);
  color: var(--c-on-dark);
  font-weight: 700;
}
.now-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--c-now);
}
</style>
