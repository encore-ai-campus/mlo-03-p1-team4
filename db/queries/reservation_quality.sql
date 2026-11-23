-- #119 전체 스키마 정합성 점검. 모든 값이 0이어야 한다.
SELECT 'missing_payment' AS check_name, COUNT(*) AS problem_count
  FROM reservations AS r
  LEFT JOIN payments AS p ON p.reservation_id = r.reservation_id
 WHERE p.payment_id IS NULL
UNION ALL
SELECT 'cancelled_without_refund', COUNT(*)
  FROM reservations AS r
  JOIN payments AS p ON p.reservation_id = r.reservation_id
 WHERE r.status = 'cancelled' AND p.status <> 'refunded'
UNION ALL
SELECT 'noncancelled_refunded', COUNT(*)
  FROM reservations AS r
  JOIN payments AS p ON p.reservation_id = r.reservation_id
 WHERE r.status <> 'cancelled' AND p.status = 'refunded'
UNION ALL
SELECT 'cancelled_with_slots', COUNT(*)
  FROM reservation_slots AS s
  JOIN reservations AS r ON r.reservation_id = s.reservation_id
 WHERE r.status = 'cancelled'
UNION ALL
SELECT 'active_slot_count_mismatch', COUNT(*)
  FROM reservations AS r
  LEFT JOIN (
      SELECT reservation_id, COUNT(*) AS slot_count
        FROM reservation_slots GROUP BY reservation_id
  ) AS slots ON slots.reservation_id = r.reservation_id
 WHERE r.status IN ('confirmed', 'completed')
   AND COALESCE(slots.slot_count, 0) <> r.end_hour - r.start_hour;
