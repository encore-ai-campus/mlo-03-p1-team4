// F-60 MongoDB 초기화. 현재 Compass의 space_rental_analytics.events 구조를 기준으로 한다.
// 실행: mongosh <연결주소> docs/db/mongo_init.js
// 테스트: MONGO_ANALYTICS_DB=space_rental_analytics_test 를 주면 운영 컬렉션과 crawl DB를 건드리지 않는다.
// 기존 spacecube.user_events와 그 문서는 삭제하거나 변환하지 않는다.

(function () {
  const analyticsName = process.env.MONGO_ANALYTICS_DB || 'space_rental_analytics';
  if (!/^space_rental_analytics(?:_test)?$/.test(analyticsName)) {
    throw new Error('MONGO_ANALYTICS_DB는 space_rental_analytics 또는 space_rental_analytics_test만 허용');
  }
  const analytics = db.getSiblingDB(analyticsName);
  const serverResults = [
    'reservation_complete',
    'reservation_conflict',
    'reservation_cancel_complete'
  ];
  const eventNames = [
    'page_view',
    'product_impression',
    'product_view',
    'product_section_click',
    'search_submit',
    'availability_view',
    'rental_slot_select',
    'reservation_start',
    'reservation_complete',
    'reservation_conflict',
    'reservation_cancel_attempt',
    'reservation_cancel_complete',
    'review_create',
    'login',
    'signup'
  ];
  const emptyProductsAllowed = ['page_view', 'search_submit', 'login', 'signup'];
  const text = { bsonType: 'string', minLength: 1 };
  const nullableText = { bsonType: ['string', 'null'] };
  const navigationEndpoint = {
    bsonType: 'object',
    required: ['page_view_id', 'site_id', 'url', 'path'],
    additionalProperties: false,
    properties: {
      page_view_id: nullableText,
      site_id: nullableText,
      url: text,
      path: nullableText
    }
  };
  const site = {
    bsonType: 'object',
    required: ['site_id', 'hostname', 'platform'],
    additionalProperties: false,
    properties: {
      site_id: text,
      hostname: text,
      platform: { enum: ['desktop_web', 'mobile_web', 'ios', 'android'] }
    }
  };
  const acquisition = {
    bsonType: 'object',
    required: ['landing_url', 'referrer_url', 'utm_source', 'utm_medium', 'utm_campaign'],
    additionalProperties: false,
    properties: {
      landing_url: text,
      referrer_url: nullableText,
      utm_source: nullableText,
      utm_medium: nullableText,
      utm_campaign: nullableText
    }
  };
  const page = {
    bsonType: 'object',
    required: ['page_view_id', 'page_type', 'url', 'path', 'title'],
    additionalProperties: false,
    properties: {
      page_view_id: text,
      page_type: text,
      url: text,
      path: text,
      title: text
    }
  };
  const navigation = {
    bsonType: 'object',
    required: ['from', 'to', 'navigation_type'],
    additionalProperties: false,
    properties: {
      from: { anyOf: [{ bsonType: 'null' }, navigationEndpoint] },
      to: navigationEndpoint,
      navigation_type: { enum: ['external', 'internal', 'direct', 'reload', 'history'] }
    }
  };
  const product = {
    bsonType: 'object',
    required: ['product_id', 'product_name', 'price', 'rental_conditions'],
    additionalProperties: false,
    properties: {
      product_id: text,
      product_name: text,
      price: {
        bsonType: 'object',
        required: ['currency', 'displayed_amount_minor', 'displayed_text', 'billing_unit'],
        additionalProperties: false,
        properties: {
          currency: { bsonType: 'string', pattern: '^[A-Z]{3}$' },
          displayed_amount_minor: { bsonType: ['int', 'long'], minimum: 0 },
          displayed_text: text,
          billing_unit: { enum: ['hour', 'day', 'night', 'session', 'total'] }
        }
      },
      rental_conditions: {
        bsonType: 'object',
        required: ['start_at', 'end_at', 'timezone', 'guest_count', 'option_ids'],
        additionalProperties: false,
        properties: {
          start_at: { bsonType: ['date', 'null'] },
          end_at: { bsonType: ['date', 'null'] },
          timezone: text,
          guest_count: { bsonType: ['int', 'long', 'null'], minimum: 1 },
          option_ids: { bsonType: 'array', items: text }
        }
      }
    }
  };
  const contextOrNull = (schema) => ({ anyOf: [{ bsonType: 'null' }, schema] });
  const eventSchema = {
    bsonType: 'object',
    required: [
      'event_id', 'schema_version', 'event_name', 'occurred_at', 'received_at',
      'user', 'site', 'acquisition', 'page', 'navigation', 'products',
      'properties', 'is_synthetic', 'server'
    ],
    additionalProperties: false,
    properties: {
      _id: { bsonType: 'objectId' },
      event_id: text,
      schema_version: { bsonType: 'int', enum: [1] },
      event_name: { enum: eventNames },
      occurred_at: { bsonType: 'date' },
      received_at: { bsonType: 'date' },
      user: {
        bsonType: 'object',
        required: ['user_id', 'anonymous_id', 'session_id', 'session_sequence'],
        additionalProperties: false,
        properties: {
          user_id: { bsonType: ['string', 'null'], minLength: 1 },
          anonymous_id: { anyOf: [{ bsonType: 'null' }, text] },
          session_id: text,
          session_sequence: {
            anyOf: [
              { bsonType: 'null' },
              { bsonType: ['int', 'long'], minimum: 1 }
            ]
          }
        }
      },
      site: contextOrNull(site),
      acquisition: contextOrNull(acquisition),
      page: contextOrNull(page),
      navigation: contextOrNull(navigation),
      products: { bsonType: 'array', items: product },
      properties: { bsonType: 'object' },
      is_synthetic: { bsonType: 'bool' },
      server: text
    }
  };
  const feContext = {
    $jsonSchema: {
      bsonType: 'object',
      properties: {
        user: {
          bsonType: 'object',
          properties: {
            anonymous_id: text,
            session_sequence: { bsonType: ['int', 'long'], minimum: 1 }
          }
        },
        site: { bsonType: 'object' },
        acquisition: { bsonType: 'object' },
        page: { bsonType: 'object' },
        navigation: { bsonType: 'object' }
      }
    }
  };
  const eventValidator = {
    $and: [
      { $jsonSchema: eventSchema },
      { $or: [{ event_name: { $in: emptyProductsAllowed } }, { 'products.0': { $exists: true } }] },
      { $or: [{ event_name: { $in: serverResults } }, feContext] }
    ]
  };
  const collectionExists = (database, name) =>
    database.getCollectionInfos({ name: name }).length !== 0;

  // 기존 문서는 보존한다. 이미 존재하는 컬렉션에는 collMod만 적용한다.
  if (collectionExists(analytics, 'events')) {
    const result = analytics.runCommand({
      collMod: 'events',
      validator: eventValidator,
      validationLevel: 'strict',
      validationAction: 'error'
    });
    if (!result.ok) throw new Error('events collMod 실패: ' + tojson(result));
  } else {
    analytics.createCollection('events', {
      validator: eventValidator,
      validationLevel: 'strict',
      validationAction: 'error'
    });
  }
  const events = analytics.getCollection('events');
  events.createIndex({ event_id: 1 }, { name: 'uq_event_id', unique: true });
  events.createIndex({ 'user.user_id': 1, occurred_at: -1 }, { name: 'user_history' });
  events.createIndex(
    { 'user.session_id': 1, 'user.session_sequence': 1 },
    { name: 'session_order' }
  );
  events.createIndex(
    { 'site.site_id': 1, 'products.product_id': 1, occurred_at: -1 },
    { name: 'site_product_history' }
  );
  events.createIndex(
    { received_at: 1 },
    { name: 'ttl_received_at_365d', expireAfterSeconds: 31536000 }
  );

  if (!collectionExists(analytics, 'event_daily')) {
    analytics.createCollection('event_daily');
  }
  analytics.getCollection('event_daily').createIndex(
    { date: 1, event_type: 1, venue_id: 1, is_synthetic: 1 },
    { unique: true }
  );

  // 크롤링 원본은 현재 Compass 구성대로 별도 crawl 데이터베이스에 둔다.
  // 분석 테스트 DB 검증 중에는 crawl DB를 수정하지 않는다.
  if (analyticsName !== 'space_rental_analytics_test') {
    const crawlDb = db.getSiblingDB('crawl');
    const crawlValidator = {
      $jsonSchema: {
        bsonType: 'object',
        required: ['source_site', 'source_id', 'crawled_at', 'status'],
        properties: {
          source_site: { bsonType: 'string' },
          source_id: { bsonType: 'string' },
          job_id: { bsonType: ['long', 'int'] },
          crawled_at: { bsonType: 'date' },
          status: { enum: ['ok', 'no_detail', 'excluded', 'registered'] },
          space_types: { bsonType: 'array' },
          extracted: {
            bsonType: 'object',
            description: '인원·가격·최소시간·영업시간·시설·시군구. 업체 실명·사진·연락처 없음'
          },
          mapped: { bsonType: ['object', 'null'] },
          exclude_reason: { bsonType: ['string', 'null'] },
          venue_id: { bsonType: ['long', 'int', 'null'] }
        }
      }
    };
    if (collectionExists(crawlDb, 'crawl_raw')) {
      const result = crawlDb.runCommand({
        collMod: 'crawl_raw',
        validator: crawlValidator,
        validationLevel: 'strict',
        validationAction: 'error'
      });
      if (!result.ok) throw new Error('crawl_raw collMod 실패: ' + tojson(result));
    } else {
      crawlDb.createCollection('crawl_raw', {
        validator: crawlValidator,
        validationLevel: 'strict',
        validationAction: 'error'
      });
    }
    const crawl = crawlDb.getCollection('crawl_raw');
    crawl.createIndex({ source_site: 1, source_id: 1 }, { unique: true });
    crawl.createIndex({ status: 1, 'mapped.category': 1 });
  }

  print('MongoDB 초기화 완료: ' + analyticsName + '.events / event_daily' +
    (analyticsName === 'space_rental_analytics_test' ? '' : ' / crawl.crawl_raw'));
})();
