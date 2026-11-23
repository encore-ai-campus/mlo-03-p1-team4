-- #119 판매: 결제일 코호트, 현재 환불 상태 기준. 금액은 예약 당시 total_price.
-- 종료일은 미포함. 날짜와 합성 데이터 포함 여부를 실행 전에 바꾼다.
SET @from_at = '2026-11-01 00:00:00';
SET @to_at = '2026-12-01 00:00:00';
SET @include_synthetic = 1;

SELECT c.code AS category_code, v.venue_id, v.name AS venue_name,
       COUNT(*) AS payment_count,
       SUM(r.total_price) AS gross_paid_krw,
       SUM(CASE WHEN p.status = 'refunded' THEN r.total_price ELSE 0 END) AS refunded_krw,
       SUM(CASE WHEN p.status = 'paid' THEN r.total_price ELSE 0 END) AS current_net_krw
  FROM payments AS p
  JOIN reservations AS r ON r.reservation_id = p.reservation_id
  JOIN venues AS v ON v.venue_id = r.venue_id
  JOIN categories AS c ON c.category_id = v.category_id
 WHERE p.paid_at >= @from_at AND p.paid_at < @to_at
   AND (@include_synthetic = 1 OR r.is_synthetic = 0)
 GROUP BY c.code, v.venue_id, v.name
 ORDER BY current_net_krw DESC, v.venue_id;
