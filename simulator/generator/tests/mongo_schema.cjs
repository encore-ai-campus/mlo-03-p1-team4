// 공식 mongosh 파일을 네트워크 없이 실행해 validator·인덱스만 추출한다.
const fs = require('node:fs');
const vm = require('node:vm');
const result = { options: null, indexes: [] };
const database = {
  getCollectionInfos() { return []; },
  createCollection(name, options) {
    if (name === 'events') result.options = options;
  },
  getCollection(name) {
    return { createIndex(keys, options) {
      if (name === 'events') result.indexes.push({ keys, options });
    } };
  },
};
vm.runInNewContext(fs.readFileSync(process.argv[2], 'utf8'), {
  db: { getSiblingDB() { return database; } },
  process: { env: { MONGO_ANALYTICS_DB: 'space_rental_analytics_test' } },
  print() {},
  tojson: JSON.stringify,
}, { timeout: 1000 });
process.stdout.write(JSON.stringify(result));
