import { createMocks } from 'node-mocks-http';

// 실제 fetch를 교체해 목 응답 주입
globalThis.fetch = async (url, opts) => {
  if (url === 'https://openrouter.ai/api/v1/credits') {
    return {
      ok: true,
      json: async () => ({ data: { total_credits: 10.5, total_usage: 3.2 } }),
    };
  }
  throw new Error(`unexpected fetch: ${url}`);
};

const { default: handler } = await import('../openrouter.js');

describe('GET /api/openrouter', () => {
  test('크레딧 정상 반환', async () => {
    const req = { method: 'GET' };
    let statusCode = 200;
    let body = null;
    const res = {
      status(code) { statusCode = code; return this; },
      json(data) { body = data; return this; },
    };

    process.env.OPENROUTER_API_KEY = 'test-key';
    await handler(req, res);

    expect(statusCode).toBe(200);
    expect(body).toEqual({ total_credits: 10.5, total_usage: 3.2 });
  });

  test('환경변수 미설정 시 500', async () => {
    delete process.env.OPENROUTER_API_KEY;
    const req = { method: 'GET' };
    let statusCode = 200;
    let body = null;
    const res = {
      status(code) { statusCode = code; return this; },
      json(data) { body = data; return this; },
    };

    await handler(req, res);

    expect(statusCode).toBe(500);
    expect(body.error).toMatch(/OPENROUTER_API_KEY/);
  });
});
