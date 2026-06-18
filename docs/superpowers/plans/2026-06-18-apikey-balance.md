# API 키 잔여량 확인 페이지 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** OpenRouter와 OpenAI API 잔여량을 한 페이지에서 확인하는 Vercel 배포 웹페이지를 만든다.

**Architecture:** 정적 HTML 프론트엔드 + Vercel 서버리스 함수 2개. 프론트는 각 함수를 호출해 결과를 카드 형태로 렌더링하며, API 키는 Vercel 환경변수에만 보관된다. OpenAI는 Admin 키로 Costs API를 호출해 기준 잔액에서 누적 사용 비용을 차감하는 추정 방식을 사용한다.

**Tech Stack:** Vanilla JavaScript (ESM), Vercel Serverless Functions (Node.js), Node.js `fetch` (내장)

## Global Constraints

- API 키(`OPENROUTER_API_KEY`, `OPENAI_ADMIN_KEY`)는 절대 코드/HTML에 하드코딩하지 않는다 — Vercel 환경변수만 사용
- 기존 `vercel.json`의 `/` → `worldcup2026.html` 리라이트를 수정하지 않는다
- 모든 코드 주석은 한국어
- 서버리스 함수는 `api/` 디렉터리에 위치 (Vercel 규약)

---

## 파일 구조

| 파일 | 역할 |
|------|------|
| `api/openrouter.js` | OpenRouter `/api/v1/credits` 프록시 |
| `api/openai-cost.js` | OpenAI `/v1/organization/costs` 프록시 (페이지네이션 처리) |
| `apikey-balance.html` | 카드 2개 UI, 새로고침, 마지막 갱신 시각, OpenAI 기준 잔액 설정 |
| `api/__tests__/openrouter.test.js` | openrouter 함수 단위 테스트 |
| `api/__tests__/openai-cost.test.js` | openai-cost 함수 단위 테스트 |
| `package.json` | 테스트 실행용 (jest) |

---

## Task 1: OpenRouter 서버리스 함수

**Files:**
- Create: `api/openrouter.js`
- Create: `api/__tests__/openrouter.test.js`
- Create: `package.json`

**Interfaces:**
- Produces: `GET /api/openrouter` → `{ total_credits: number, total_usage: number }` (200) 또는 `{ error: string }` (4xx/5xx)

- [ ] **Step 1: package.json 생성 (Jest 설정 포함)**

```json
{
  "name": "apikey-balance",
  "version": "1.0.0",
  "scripts": {
    "test": "node --experimental-vm-modules node_modules/.bin/jest"
  },
  "devDependencies": {
    "jest": "^29.0.0"
  },
  "jest": {
    "testEnvironment": "node",
    "transform": {}
  }
}
```

- [ ] **Step 2: npm install 실행**

```bash
cd /Users/maru/Agents/src/test/.claude/worktrees/apikey-balance
npm install
```

기대 결과: `node_modules/` 생성, 오류 없음.

- [ ] **Step 3: 실패하는 테스트 작성**

`api/__tests__/openrouter.test.js`:

```js
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
```

- [ ] **Step 4: 테스트 실패 확인**

```bash
npm test -- api/__tests__/openrouter.test.js
```

기대 결과: `Cannot find module '../openrouter.js'` 오류로 실패.

- [ ] **Step 5: openrouter.js 구현**

`api/openrouter.js`:

```js
export default async function handler(req, res) {
  const apiKey = process.env.OPENROUTER_API_KEY;
  if (!apiKey) {
    return res.status(500).json({ error: 'OPENROUTER_API_KEY 환경변수가 설정되지 않았습니다.' });
  }

  const response = await fetch('https://openrouter.ai/api/v1/credits', {
    headers: { Authorization: `Bearer ${apiKey}` },
  });

  if (!response.ok) {
    const text = await response.text();
    return res.status(response.status).json({ error: text });
  }

  const { data } = await response.json();
  res.status(200).json({ total_credits: data.total_credits, total_usage: data.total_usage });
}
```

- [ ] **Step 6: 테스트 통과 확인**

```bash
npm test -- api/__tests__/openrouter.test.js
```

기대 결과: 2개 테스트 모두 PASS.

- [ ] **Step 7: 커밋**

```bash
git add api/openrouter.js api/__tests__/openrouter.test.js package.json package-lock.json
git commit -m "feat: OpenRouter 크레딧 조회 서버리스 함수 추가"
```

---

## Task 2: OpenAI Costs 서버리스 함수

**Files:**
- Create: `api/openai-cost.js`
- Create: `api/__tests__/openai-cost.test.js`

**Interfaces:**
- Consumes: 쿼리 파라미터 `start_time` (Unix timestamp, 초 단위)
- Produces: `GET /api/openai-cost?start_time=<unix>` → `{ total_cost: number }` (200) 또는 `{ error: string }` (4xx/5xx)

- [ ] **Step 1: 실패하는 테스트 작성**

`api/__tests__/openai-cost.test.js`:

```js
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
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
npm test -- api/__tests__/openai-cost.test.js
```

기대 결과: `Cannot find module '../openai-cost.js'` 오류로 실패.

- [ ] **Step 3: openai-cost.js 구현**

`api/openai-cost.js`:

```js
export default async function handler(req, res) {
  const adminKey = process.env.OPENAI_ADMIN_KEY;
  if (!adminKey) {
    return res.status(500).json({ error: 'OPENAI_ADMIN_KEY 환경변수가 설정되지 않았습니다.' });
  }

  const startTime = req.query?.start_time;
  if (!startTime) {
    return res.status(400).json({ error: 'start_time 쿼리 파라미터가 필요합니다.' });
  }

  let totalCost = 0;
  let url = `https://api.openai.com/v1/organization/costs?start_time=${startTime}&limit=30`;

  // 페이지네이션이 있는 경우 모든 페이지 순회
  while (url) {
    const response = await fetch(url, {
      headers: { Authorization: `Bearer ${adminKey}` },
    });

    if (!response.ok) {
      const text = await response.text();
      return res.status(response.status).json({ error: text });
    }

    const page = await response.json();

    for (const bucket of page.data) {
      for (const result of bucket.results) {
        totalCost += result.amount.value;
      }
    }

    url = page.has_more && page.next_page
      ? `https://api.openai.com/v1/organization/costs?start_time=${startTime}&limit=30&page=${page.next_page}`
      : null;
  }

  res.status(200).json({ total_cost: totalCost });
}
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
npm test -- api/__tests__/openai-cost.test.js
```

기대 결과: 4개 테스트 모두 PASS.

- [ ] **Step 5: 커밋**

```bash
git add api/openai-cost.js api/__tests__/openai-cost.test.js
git commit -m "feat: OpenAI Costs API 서버리스 함수 추가 (페이지네이션 처리)"
```

---

## Task 3: 프론트엔드 HTML 페이지

**Files:**
- Create: `apikey-balance.html`

**Interfaces:**
- Consumes: `GET /api/openrouter` → `{ total_credits, total_usage }`
- Consumes: `GET /api/openai-cost?start_time=<unix>` → `{ total_cost }`
- Consumes/Produces: `localStorage` 키 `openai_base_amount` (string, USD 금액), `openai_base_date` (string, YYYY-MM-DD)

- [ ] **Step 1: apikey-balance.html 작성**

`apikey-balance.html`:

```html
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>API 잔여량</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: #0f1117;
      color: #e2e8f0;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 2rem 1rem;
    }

    header {
      width: 100%;
      max-width: 760px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 2rem;
    }

    header h1 { font-size: 1.25rem; font-weight: 600; color: #f8fafc; }

    .header-right { display: flex; flex-direction: column; align-items: flex-end; gap: 0.25rem; }

    #last-updated { font-size: 0.75rem; color: #64748b; }

    button.refresh {
      background: #1e293b;
      border: 1px solid #334155;
      color: #94a3b8;
      padding: 0.4rem 0.9rem;
      border-radius: 6px;
      font-size: 0.8rem;
      cursor: pointer;
      transition: background 0.15s;
    }
    button.refresh:hover { background: #273548; color: #e2e8f0; }
    button.refresh:disabled { opacity: 0.5; cursor: not-allowed; }

    .cards {
      width: 100%;
      max-width: 760px;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      gap: 1.25rem;
    }

    .card {
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 12px;
      padding: 1.5rem;
    }

    .card-header {
      display: flex;
      align-items: center;
      gap: 0.6rem;
      margin-bottom: 1.25rem;
    }

    .card-logo { width: 24px; height: 24px; border-radius: 4px; object-fit: contain; }

    .card-title { font-size: 0.95rem; font-weight: 600; color: #cbd5e1; }

    .balance-label { font-size: 0.75rem; color: #64748b; margin-bottom: 0.25rem; }

    .balance-amount {
      font-size: 2.4rem;
      font-weight: 700;
      color: #f8fafc;
      letter-spacing: -0.02em;
      margin-bottom: 0.2rem;
    }

    .balance-amount.error { font-size: 1rem; color: #f87171; font-weight: 400; }

    .balance-sub { font-size: 0.75rem; color: #64748b; margin-bottom: 1rem; }

    .progress-wrap { margin-bottom: 1rem; }
    .progress-bar-bg {
      background: #0f1117;
      border-radius: 9999px;
      height: 6px;
      overflow: hidden;
    }
    .progress-bar-fill {
      height: 100%;
      border-radius: 9999px;
      transition: width 0.4s ease;
      background: #3b82f6;
    }
    .progress-bar-fill.warning { background: #f59e0b; }
    .progress-bar-fill.danger  { background: #ef4444; }

    .progress-label {
      display: flex;
      justify-content: space-between;
      font-size: 0.7rem;
      color: #475569;
      margin-top: 0.35rem;
    }

    /* OpenAI 설정 섹션 */
    .settings {
      border-top: 1px solid #334155;
      padding-top: 1rem;
      margin-top: 0.25rem;
    }

    .settings-title {
      font-size: 0.7rem;
      color: #475569;
      margin-bottom: 0.6rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    .settings-row { display: flex; gap: 0.5rem; margin-bottom: 0.5rem; }

    .settings-row label { font-size: 0.75rem; color: #94a3b8; white-space: nowrap; align-self: center; min-width: 60px; }

    .settings-row input {
      flex: 1;
      background: #0f1117;
      border: 1px solid #334155;
      border-radius: 6px;
      color: #e2e8f0;
      font-size: 0.8rem;
      padding: 0.3rem 0.5rem;
    }

    .settings-row input:focus { outline: none; border-color: #3b82f6; }

    button.save-settings {
      width: 100%;
      background: #2563eb;
      border: none;
      color: #fff;
      padding: 0.45rem;
      border-radius: 6px;
      font-size: 0.8rem;
      cursor: pointer;
      transition: background 0.15s;
    }
    button.save-settings:hover { background: #1d4ed8; }

    .badge-estimated {
      font-size: 0.65rem;
      background: #1e3a5f;
      color: #93c5fd;
      padding: 0.1rem 0.4rem;
      border-radius: 4px;
      margin-left: 0.4rem;
      vertical-align: middle;
    }
  </style>
</head>
<body>

<header>
  <h1>API 잔여량</h1>
  <div class="header-right">
    <span id="last-updated">—</span>
    <button class="refresh" id="btn-refresh">새로고침</button>
  </div>
</header>

<div class="cards">

  <!-- OpenRouter 카드 -->
  <div class="card" id="card-openrouter">
    <div class="card-header">
      <svg class="card-logo" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect width="24" height="24" rx="4" fill="#6d28d9"/>
        <path d="M6 12h12M12 6l6 6-6 6" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      <span class="card-title">OpenRouter</span>
    </div>
    <div class="balance-label">남은 크레딧</div>
    <div class="balance-amount" id="or-remaining">—</div>
    <div class="balance-sub" id="or-sub">로딩 중...</div>
    <div class="progress-wrap">
      <div class="progress-bar-bg">
        <div class="progress-bar-fill" id="or-bar" style="width:0%"></div>
      </div>
      <div class="progress-label">
        <span id="or-pct-label">사용 0%</span>
        <span id="or-total-label">총 $0</span>
      </div>
    </div>
  </div>

  <!-- OpenAI 카드 -->
  <div class="card" id="card-openai">
    <div class="card-header">
      <svg class="card-logo" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect width="24" height="24" rx="4" fill="#10a37f"/>
        <path d="M12 4.5a4.5 4.5 0 0 1 4.5 4.5c0 1.08-.38 2.07-1.01 2.84L18 14.25l-1.5 1.5-2.41-2.41A4.47 4.47 0 0 1 12 13.5a4.5 4.5 0 1 1 0-9z" fill="#fff" opacity=".9"/>
      </svg>
      <span class="card-title">OpenAI<span class="badge-estimated">추정</span></span>
    </div>
    <div class="balance-label">추정 잔액</div>
    <div class="balance-amount" id="oa-remaining">—</div>
    <div class="balance-sub" id="oa-sub">기준 잔액과 날짜를 설정하세요</div>
    <div class="progress-wrap">
      <div class="progress-bar-bg">
        <div class="progress-bar-fill" id="oa-bar" style="width:0%"></div>
      </div>
      <div class="progress-label">
        <span id="oa-pct-label">사용 0%</span>
        <span id="oa-total-label">기준 $0</span>
      </div>
    </div>

    <div class="settings">
      <div class="settings-title">기준 설정</div>
      <div class="settings-row">
        <label for="oa-base-amount">기준 잔액</label>
        <input id="oa-base-amount" type="number" min="0" step="0.01" placeholder="예: 20.00" />
      </div>
      <div class="settings-row">
        <label for="oa-base-date">기준 날짜</label>
        <input id="oa-base-date" type="date" />
      </div>
      <button class="save-settings" id="btn-save-settings">저장 후 새로고침</button>
    </div>
  </div>

</div>

<script type="module">
  const $ = id => document.getElementById(id);

  // 숫자 포맷: $12.34
  function fmt(n) {
    return '$' + n.toFixed(2);
  }

  // 진행 바 색상 결정 (사용률 기준)
  function barClass(pct) {
    if (pct >= 90) return 'danger';
    if (pct >= 70) return 'warning';
    return '';
  }

  // localStorage에서 OpenAI 기준 설정 로드
  function loadOASettings() {
    return {
      amount: parseFloat(localStorage.getItem('openai_base_amount') || '0'),
      date: localStorage.getItem('openai_base_date') || '',
    };
  }

  // 페이지 로드 시 입력 필드 복원
  function restoreOAInputs() {
    const { amount, date } = loadOASettings();
    if (amount) $('oa-base-amount').value = amount;
    if (date)   $('oa-base-date').value = date;
  }

  // OpenRouter 카드 갱신
  async function refreshOpenRouter() {
    $('or-remaining').className = 'balance-amount';
    $('or-remaining').textContent = '로딩 중...';
    $('or-sub').textContent = '';

    try {
      const res = await fetch('/api/openrouter');
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);

      const remaining = data.total_credits - data.total_usage;
      const pct = data.total_credits > 0
        ? Math.min(100, (data.total_usage / data.total_credits) * 100)
        : 0;

      $('or-remaining').textContent = fmt(remaining);
      $('or-sub').textContent = `사용 ${fmt(data.total_usage)} / 충전 ${fmt(data.total_credits)}`;
      $('or-bar').style.width = pct + '%';
      $('or-bar').className = 'progress-bar-fill ' + barClass(pct);
      $('or-pct-label').textContent = `사용 ${pct.toFixed(1)}%`;
      $('or-total-label').textContent = `총 ${fmt(data.total_credits)}`;
    } catch (e) {
      $('or-remaining').className = 'balance-amount error';
      $('or-remaining').textContent = e.message;
      $('or-sub').textContent = '';
    }
  }

  // OpenAI 카드 갱신
  async function refreshOpenAI() {
    const { amount: baseAmount, date: baseDate } = loadOASettings();

    $('oa-remaining').className = 'balance-amount';

    if (!baseAmount || !baseDate) {
      $('oa-remaining').textContent = '—';
      $('oa-sub').textContent = '기준 잔액과 날짜를 입력하세요';
      return;
    }

    $('oa-remaining').textContent = '로딩 중...';
    $('oa-sub').textContent = '';

    try {
      const startUnix = Math.floor(new Date(baseDate).getTime() / 1000);
      const res = await fetch(`/api/openai-cost?start_time=${startUnix}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);

      const remaining = baseAmount - data.total_cost;
      const pct = baseAmount > 0
        ? Math.min(100, (data.total_cost / baseAmount) * 100)
        : 0;

      $('oa-remaining').textContent = fmt(remaining);
      $('oa-sub').textContent = `사용 ${fmt(data.total_cost)} / 기준 ${fmt(baseAmount)} (${baseDate} 이후)`;
      $('oa-bar').style.width = pct + '%';
      $('oa-bar').className = 'progress-bar-fill ' + barClass(pct);
      $('oa-pct-label').textContent = `사용 ${pct.toFixed(1)}%`;
      $('oa-total-label').textContent = `기준 ${fmt(baseAmount)}`;
    } catch (e) {
      $('oa-remaining').className = 'balance-amount error';
      $('oa-remaining').textContent = e.message;
      $('oa-sub').textContent = '';
    }
  }

  // 전체 새로고침
  async function refreshAll() {
    $('btn-refresh').disabled = true;
    await Promise.all([refreshOpenRouter(), refreshOpenAI()]);
    $('last-updated').textContent = '갱신: ' + new Date().toLocaleTimeString('ko-KR');
    $('btn-refresh').disabled = false;
  }

  // OpenAI 설정 저장
  $('btn-save-settings').addEventListener('click', () => {
    const amount = $('oa-base-amount').value;
    const date   = $('oa-base-date').value;
    if (!amount || !date) { alert('기준 잔액과 날짜를 모두 입력하세요.'); return; }
    localStorage.setItem('openai_base_amount', amount);
    localStorage.setItem('openai_base_date', date);
    refreshAll();
  });

  $('btn-refresh').addEventListener('click', refreshAll);

  // 페이지 진입 시 자동 새로고침
  restoreOAInputs();
  refreshAll();
</script>

</body>
</html>
```

- [ ] **Step 2: 브라우저에서 확인 (로컬 Vercel dev 필요)**

Vercel CLI가 설치되어 있다면:
```bash
# 환경변수 설정 후
OPENROUTER_API_KEY=sk-or-... OPENAI_ADMIN_KEY=sk-admin-... vercel dev
```
브라우저에서 `http://localhost:3000/apikey-balance.html` 접속. 두 카드 모두 로딩 후 숫자가 표시되는지 확인. 환경변수 없이 접속 시 카드에 에러 메시지가 표시되는지 확인.

- [ ] **Step 3: 커밋**

```bash
git add apikey-balance.html
git commit -m "feat: API 잔여량 확인 프론트엔드 페이지 추가"
```

---

## Task 4: .gitignore 확인 및 최종 검토

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: .gitignore에 node_modules 포함 여부 확인 및 추가**

```bash
cat .gitignore
```

`node_modules`가 없으면:
```bash
echo "node_modules/" >> .gitignore
git add .gitignore
git commit -m "chore: node_modules gitignore 추가"
```

- [ ] **Step 2: 전체 테스트 통과 확인**

```bash
npm test
```

기대 결과: 6개 테스트 모두 PASS (openrouter 2개 + openai-cost 4개).

- [ ] **Step 3: 최종 커밋 없음 — 이미 각 태스크에서 커밋 완료**

---

## Vercel 배포 시 필요한 환경변수

배포 전 Vercel 대시보드 또는 CLI에서 두 키를 설정해야 한다:

```bash
vercel env add OPENROUTER_API_KEY
vercel env add OPENAI_ADMIN_KEY
```
