-- #119 취소: 예약 생성일 코호트의 현재 상태. 취소일별 추이는 별도 이벤트를 사용한다.
SET @from_at = '2026-11-01 00:00:00';
SET @to_at = '2026-12-01 00:00:00';
SET @include_synthetic = 1;

SELECT c.code AS category_code, v.venue_id, v.name AS venue_name,
       COUNT(*) AS created_reservations,
       SUM(r.status = 'cancelled') AS cancelled_reservations,
       ROUND(100 * SUM(r.status = 'cancelled') / NULLIF(COUNT(*), 0), 2)
         AS current_cancel_rate_pct,
       SUM(CASE WHEN p.status = 'refunded' THEN r.total_price ELSE 0 END)
         AS refunded_krw
  FROM reservations AS r
  JOIN payments AS p ON p.reservation_id = r.reservation_id
  JOIN venues AS v ON v.venue_id = r.venue_id
  JOIN categories AS c ON c.category_id = v.category_id
 WHERE r.created_at >= @from_at AND r.created_at < @to_at
   AND (@include_synthetic = 1 OR r.is_synthetic = 0)
 GROUP BY c.code, v.venue_id, v.name
 ORDER BY cancelled_reservations DESC, v.venue_id;
