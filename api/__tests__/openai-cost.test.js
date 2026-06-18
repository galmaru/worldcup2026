// 페이지네이션 없는 단순 응답
const singlePageResponse = {
  object: 'page',
  data: [
    { object: 'bucket', start_time: 1700000000, end_time: 1700086400,
      results: [{ object: 'costs', amount: { value: 1.5, currency: 'usd' }, line_item: null }] },
    { object: 'bucket', start_time: 1700086400, end_time: 1700172800,
      results: [{ object: 'costs', amount: { value: 0.8, currency: 'usd' }, line_item: null }] },
  ],
  has_more: false,
  next_page: null,
};

// 페이지네이션 있는 응답
const page1Response = {
  object: 'page',
  data: [
    { object: 'bucket', start_time: 1700000000, end_time: 1700086400,
      results: [{ object: 'costs', amount: { value: 2.0, currency: 'usd' }, line_item: null }] },
  ],
  has_more: true,
  next_page: 'page_token_abc',
};
const page2Response = {
  object: 'page',
  data: [
    { object: 'bucket', start_time: 1700086400, end_time: 1700172800,
      results: [{ object: 'costs', amount: { value: 1.0, currency: 'usd' }, line_item: null }] },
  ],
  has_more: false,
  next_page: null,
};

let fetchCallUrls = [];
globalThis.fetch = async (url) => {
  fetchCallUrls.push(url);
  if (url.includes('page=page_token_abc')) return { ok: true, json: async () => page2Response };
  if (url.includes('start_time=')) return { ok: true, json: async () => page1Response };
  throw new Error(`unexpected fetch: ${url}`);
};

const { default: handler } = await import('../openai-cost.js');

describe('GET /api/openai-cost', () => {
  beforeEach(() => { fetchCallUrls = []; });

  test('단일 페이지 비용 합산', async () => {
    globalThis.fetch = async () => ({ ok: true, json: async () => singlePageResponse });
    process.env.OPENAI_ADMIN_KEY = 'test-admin-key';
    const req = { method: 'GET', query: { start_time: '1700000000' } };
    let statusCode = 200; let body = null;
    const res = { status(c) { statusCode = c; return this; }, json(d) { body = d; return this; } };

    await handler(req, res);

    expect(statusCode).toBe(200);
    expect(body.total_cost).toBeCloseTo(2.3, 5);
  });

  test('페이지네이션 전체 순회', async () => {
    let callCount = 0;
    globalThis.fetch = async (url) => {
      callCount++;
      if (callCount === 1) return { ok: true, json: async () => page1Response };
      return { ok: true, json: async () => page2Response };
    };
    process.env.OPENAI_ADMIN_KEY = 'test-admin-key';
    const req = { method: 'GET', query: { start_time: '1700000000' } };
    let statusCode = 200; let body = null;
    const res = { status(c) { statusCode = c; return this; }, json(d) { body = d; return this; } };

    await handler(req, res);

    expect(statusCode).toBe(200);
    expect(body.total_cost).toBeCloseTo(3.0, 5);
    expect(callCount).toBe(2);
  });

  test('환경변수 미설정 시 500', async () => {
    delete process.env.OPENAI_ADMIN_KEY;
    const req = { method: 'GET', query: { start_time: '1700000000' } };
    let statusCode = 200; let body = null;
    const res = { status(c) { statusCode = c; return this; }, json(d) { body = d; return this; } };

    await handler(req, res);

    expect(statusCode).toBe(500);
    expect(body.error).toMatch(/OPENAI_ADMIN_KEY/);
  });

  test('start_time 누락 시 400', async () => {
    process.env.OPENAI_ADMIN_KEY = 'test-admin-key';
    const req = { method: 'GET', query: {} };
    let statusCode = 200; let body = null;
    const res = { status(c) { statusCode = c; return this; }, json(d) { body = d; return this; } };

    await handler(req, res);

    expect(statusCode).toBe(400);
    expect(body.error).toMatch(/start_time/);
  });
});
