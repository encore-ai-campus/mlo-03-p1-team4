<script setup>


// 후기 한 개. showRoom이면 어느 공간 후기인지 작은 그림과 이름을 같이 보여 준다.
defineProps({
  review: { type: Object, required: true },
  showRoom: { type: Boolean, default: false },
})
</script>

<template>
  <article class="review">
    <RouterLink v-if="showRoom" :to="`/venues/${review.venue_id}`" class="review__room"><strong>{{ review.venue_name }}</strong></RouterLink>
    <div class="review__meta">
      <span class="review__stars" :aria-label="`별점 ${review.rating}점`">{{ '★'.repeat(review.rating) }}<span class="review__off">{{ '★'.repeat(5 - review.rating) }}</span></span>
      <span class="review__by num">{{ review.author }} · {{ review.created_at?.slice(0, 10) }}</span>
    </div>
    <p class="review__text">{{ review.content }}</p>
  </article>
</template>

<style scoped>
.review {
  display: flex;
  flex-direction: column;
  gap: var(--sp-8);
}
.review__room {
  display: flex;
  align-items: center;
  gap: var(--sp-12);
}
.review__thumb {
  flex: none;
  width: 64px;
  border-radius: var(--r-sm);
  overflow: hidden;
}
.review__room-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
  font-size: var(--fs-15);
}
.review__type {
  font-size: var(--fs-12);
  font-weight: 700;
  color: var(--c-brand-ink);
}
.review__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--sp-8);
  font-size: var(--fs-13);
}
.review__stars {
  color: var(--c-star-ink);
  letter-spacing: 1px;
}
.review__off {
  color: var(--c-star-off);
}
.review__by {
  color: var(--c-subtle);
}
.review__text {
  font-size: var(--fs-15);
  line-height: 1.7;
  color: var(--c-ink-2);
}
.review__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.review__tags li {
  padding: 2px 8px;
  border-radius: 6px;
  background: var(--c-fill-soft);
  font-size: var(--fs-12);
  color: var(--c-muted);
}
</style>
