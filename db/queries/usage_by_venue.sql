-- #119 이용: 이용일 코호트. 완료는 예약 상태이며 실제 입장 확인 자료는 아니다.
SET @from_date = '2026-11-01';
SET @to_date = '2026-12-01';
SET @include_synthetic = 1;

SELECT c.code AS category_code, v.venue_id, v.name AS venue_name,
       COUNT(*) AS reservation_count,
       SUM(r.status = 'completed') AS completed_count,
       SUM(r.status = 'confirmed') AS confirmed_count,
       SUM(r.status = 'cancelled') AS cancelled_count,
       SUM(CASE WHEN r.status = 'completed' THEN r.end_hour - r.start_hour ELSE 0 END)
         AS completed_reserved_hours,
       SUM(CASE WHEN r.status IN ('confirmed', 'completed')
                THEN r.end_hour - r.start_hour ELSE 0 END) AS active_reserved_hours,
       SUM(CASE WHEN r.status = 'completed' THEN r.headcount ELSE 0 END)
         AS completed_booked_headcount
  FROM reservations AS r
  JOIN venues AS v ON v.venue_id = r.venue_id
  JOIN categories AS c ON c.category_id = v.category_id
 WHERE r.reserve_date >= @from_date AND r.reserve_date < @to_date
   AND (@include_synthetic = 1 OR r.is_synthetic = 0)
 GROUP BY c.code, v.venue_id, v.name
 ORDER BY completed_reserved_hours DESC, v.venue_id;
