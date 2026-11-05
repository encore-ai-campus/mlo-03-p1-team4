<script setup>
import { computed } from 'vue'

// 시간대별 평균 예약률 막대 (단일 계열). 80% 이상은 진한 색 + 값 표시, 나머지는 마우스·포커스 때 값 표시.
// 색: --c-brand-light / --c-brand 모두 흰 바탕 대비 3:1 이상 (dataviz validate_palette.js로 확인)
const props = defineProps({
  values: { type: Array, required: true }, // 09시부터 1시간 단위 %
  startHour: { type: Number, default: 9 },
  visible: { type: Boolean, default: true }, // 스크롤 리빌: true가 되면 막대가 바닥에서 올라온다
})
const PEAK = 80
const bars = computed(() =>
  props.values.map((v, i) => ({
    v,
    hour: props.startHour + i,
    label: `${props.startHour + i}시`,
    peak: v >= PEAK,
  })),
)
const peakHours = computed(() => bars.value.filter((b) => b.peak).map((b) => b.label).join(', '))
</script>

<template>
  <figure class="chart">
    <div class="chart__plot" :class="{ 'is-visible': visible }" aria-hidden="true">
      <div v-for="(b, i) in bars" :key="b.hour" class="chart__col" :style="{ '--i': i }">
        <span class="chart__value num" :class="{ 'is-peak': b.peak }">{{ b.v }}%</span>
        <span class="chart__bar" :class="{ 'is-peak': b.peak }" :style="{ height: `${b.v}%` }" />
        <span class="chart__hour num">{{ b.label }}</span>
      </div>
    </div>
    <figcaption class="chart__caption">진한 막대는 예약률 {{ PEAK }}% 이상인 시간대예요: {{ peakHours }}</figcaption>
    <!-- 화면 읽기 프로그램용 표 (표 자체에 sr-only를 주면 행이 빠져나와 페이지 높이를 늘린다) -->
    <div class="sr-only">
      <table>
        <caption>시간대별 평균 예약률</caption>
        <thead><tr><th scope="col">시간</th><th scope="col">예약률</th></tr></thead>
        <tbody>
          <tr v-for="b in bars" :key="b.hour"><td>{{ b.label }}</td><td>{{ b.v }}%</td></tr>
        </tbody>
      </table>
    </div>
  </figure>
</template>

<style scoped>
.chart {
  margin: 0;
}
.chart__plot {
  display: grid;
  grid-template-columns: repeat(14, minmax(0, 1fr));
  gap: 2px;
  height: 220px;
  padding-top: 24px;
  border-bottom: 1px solid var(--c-line-strong); /* taste-skill-ignore 차트 기준선 */
}
.chart__col {
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  align-items: center;
  height: 100%;
}
.chart__bar {
  flex: none;
  width: min(100%, 30px);
  border-radius: 4px 4px 0 0;
  background: var(--c-brand-light);
  transform: scaleY(0);
  transform-origin: bottom;
  transition: transform var(--t-enter) var(--ease-out);
  transition-delay: calc(var(--i) * 30ms);
}
.chart__bar.is-peak {
  background: var(--c-brand);
}
.is-visible .chart__bar {
  transform: scaleY(1);
}
/* 값은 막대 바로 위 (막대가 위쪽 여백까지 밀어 올림) */
.chart__value {
  flex: none;
  margin-bottom: 4px;
  font-size: var(--fs-12);
  line-height: 16px;
  color: var(--c-muted);
  opacity: 0;
  transition: opacity var(--t-fast);
  pointer-events: none;
}
.chart__value.is-peak,
.chart__col:hover .chart__value {
  opacity: 1;
}
.chart__value.is-peak {
  color: var(--c-ink);
  font-weight: 700;
}
.chart__hour {
  position: absolute;
  bottom: -24px;
  font-size: var(--fs-12);
  color: var(--c-subtle);
}
.chart__caption {
  margin-top: 36px;
  font-size: var(--fs-13);
  color: var(--c-muted);
}
@media (max-width: 479px) {
  .chart__hour {
    font-size: 10px;
  }
}
</style>
