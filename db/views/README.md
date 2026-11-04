# views — 백엔드가 읽는 뷰

## v_venue_rating (A 후기 요약, B 검색·상세·평점순)

공간별 평균 별점과 후기 수입니다. 후기는 예약을 거쳐 공간과 이어지므로(reviews → reservations → venues) 뷰로 묶어 둡니다. 정의는 `migrations/0001_init.sql` 끝에 있습니다.

```sql
CREATE OR REPLACE VIEW v_venue_rating AS
SELECT r.venue_id,
       ROUND(AVG(v.rating), 1) AS rating_avg,
       COUNT(*)                AS review_count
  FROM reviews v
  JOIN reservations r ON r.reservation_id = v.reservation_id
 WHERE v.deleted_at IS NULL
 GROUP BY r.venue_id;
```

- 후기가 없는 공간은 뷰에 행이 없습니다. 백엔드는 `LEFT JOIN`하고 `rating_avg = NULL`, `review_count = 0`으로 보냅니다.
- 후기가 많아져 검색이 느려지면 venues에 요약 칸을 두고 배치로 갱신하는 방식을 검토합니다.

## 나중에 만들 수 있는 뷰

| 뷰 | 용도 |
| --- | --- |
| `v_venue_weekly_bookings` | 인기도(최근 7일 예약 수) 정렬 |
| `v_hourly_occupancy` | 몰리는 시간대 차트 (메인 화면) |
