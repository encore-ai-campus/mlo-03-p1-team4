import { USE_MOCK, mockDelay, request, query } from './client';
import { reviews, reservations, users, currentUser, venueRequired, pageOf, fail, reservationItem, stamp } from './mock/db';
import { addDays, todayISO } from '@/utils/date';
function item(r) {
  const v = venueRequired(r.venue_id), author = users.find(u => u.user_id === r.user_id);
  return {
    review_id: r.review_id, venue_id: r.venue_id, venue_name: v.name, category: v.category.code, rating: r.rating, content: r.content, author: author?.deleted ? '탈퇴한 회원' : author ? `${author.name.slice(0, 1)}**` : r.author, created_at: r.created_at
  };
}
function valid(body) {
  if (!Number.isInteger(body.rating) || body.rating < 1 || body.rating > 5 || !body.content?.trim())
    fail('VALIDATION', 400, '입력한 내용을 다시 확인해 주세요.', {
      fields: [{
          field: !body.content?.trim() ? 'content' : 'rating', reason: '별점과 후기 내용을 확인해 주세요.'
        }]
    });
}
export async function getReviews(params = {}) {
  if (!USE_MOCK)
    return request(`/reviews?${query(params)}`);
  const { category, sort = 'recent' } = params;
  if (!['recent', 'high', 'low'].includes(sort))
    fail('VALIDATION', 400, '입력한 내용을 다시 확인해 주세요.');
  let list = reviews.filter(r => !r.deleted).map(item).filter(r => !category || category === 'all' || r.category === category);
  list.sort((a, b) => sort === 'high' ? b.rating - a.rating : sort === 'low' ? a.rating - b.rating : Date.parse(b.created_at) - Date.parse(a.created_at));
  return mockDelay(pageOf(list, params));
}
export async function getVenueReviews(id, params = {}) {
  if (!USE_MOCK)
    return request(`/venues/${id}/reviews?${query(params)}`);
  venueRequired(id);
  return mockDelay(pageOf(reviews.filter(r => !r.deleted && r.venue_id === Number(id)).map(item).sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at)), params));
}
export async function getMyReviews(token, params = {}) {
  if (!USE_MOCK)
    return request(`/users/me/reviews?${query(params)}`, {
      token
    });
  const user = currentUser(token);
  return mockDelay(pageOf(reviews.filter(r => !r.deleted && r.user_id === user.user_id).map(item), params));
}
export async function createReview(id, body, token) {
  if (!USE_MOCK)
    return request(`/reservations/${id}/review`, {
      method: 'POST', body, token
    });
  const user = currentUser(token);
  const r = reservations.find(r => r.reservation_id === Number(id) && r.user_id === user.user_id);
  if (!r)
    fail('RESERVATION_NOT_FOUND', 404, '예약을 찾을 수 없어요.');
  if (reservationItem(r).status !== 'completed')
    fail('NOT_COMPLETED', 403, '이용이 끝난 뒤에 후기를 쓸 수 있어요.');
  const deadline = addDays([r.date, new Intl.DateTimeFormat('en-CA', {
      timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit'
    }).format(new Date(r.created_at))].sort().at(-1), 7);
  if (deadline < todayISO())
    fail('REVIEW_PERIOD_OVER', 403, '후기를 쓸 수 있는 기간이 지났어요.', {
      deadline
    });
  const exists = reviews.find(x => x.reservation_id === r.reservation_id);
  if (exists)
    fail('REVIEW_EXISTS', 409, '이미 후기를 썼어요.', {
      review_id: exists.review_id
    });
  valid(body);
  const review = {
    review_id: Math.max(0, ...reviews.map(x => x.review_id)) + 1, reservation_id: r.reservation_id, user_id: user.user_id, venue_id: r.venue_id, rating: body.rating, content: body.content.trim(), created_at: stamp()
  };
  reviews.unshift(review);
  return mockDelay(item(review));
}
function owned(id, token) {
  const user = currentUser(token), r = reviews.find(r => r.review_id === Number(id) && !r.deleted);
  if (!r)
    fail('REVIEW_NOT_FOUND', 404, '후기를 찾을 수 없어요.');
  if (r.user_id !== user.user_id)
    fail('FORBIDDEN', 403, '이 작업은 할 수 없어요.');
  return r;
}
export async function updateReview(id, body, token) {
  if (!USE_MOCK)
    return request(`/reviews/${id}`, {
      method: 'PATCH', body, token
    });
  const r = owned(id, token);
  valid({
    ...r, ...body
  });
  for (const key of ['rating', 'content'])
    if (body[key] !== undefined)
      r[key] = body[key];
  return mockDelay(item(r));
}
export async function deleteReview(id, token) {
  if (!USE_MOCK)
    return request(`/reviews/${id}`, {
      method: 'DELETE', token
    });
  owned(id, token).deleted = true;
  return mockDelay(null);
}
