// #119 읽기 전용: 단계별 이벤트 수와 고유 세션 수. 실제 전환율 계산은 하지 않는다.
// 실행 예: mongosh "$MONGO_URL" --file db/queries/event_behavior.js
// 날짜는 한국 시간 하루 경계에 해당하는 UTC 범위. 필요 기간으로 바꾼다.
const fromUtc = ISODate('2026-10-31T15:00:00Z');
const toUtc = ISODate('2026-11-30T15:00:00Z');
const includeSynthetic = true;
const analytics = db.getSiblingDB('space_rental_analytics');
const stages = [
  'product_impression', 'product_view', 'reservation_start',
  'reservation_complete', 'reservation_conflict', 'reservation_cancel_complete'
];

analytics.events.aggregate([
  { $match: {
    occurred_at: { $gte: fromUtc, $lt: toUtc },
    event_name: { $in: stages },
    ...(includeSynthetic ? {} : { is_synthetic: false })
  } },
  { $unwind: '$products' },
  { $group: {
    _id: {
      event_name: '$event_name',
      product_id: '$products.product_id',
      session_id: '$user.session_id'
    },
    event_count: { $sum: 1 }
  } },
  { $group: {
    _id: { event_name: '$_id.event_name', product_id: '$_id.product_id' },
    event_count: { $sum: '$event_count' },
    session_count: { $sum: 1 }
  } },
  { $sort: { '_id.product_id': 1, '_id.event_name': 1 } }
], { allowDiskUse: true }).forEach(row => print(JSON.stringify(row)));
