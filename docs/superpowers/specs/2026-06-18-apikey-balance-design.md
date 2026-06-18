# API 키 잔여량 확인 웹페이지 — 설계

작성일: 2026-06-18

## 목적

OpenRouter와 OpenAI의 API 잔여량을 한 페이지에서 확인한다. Vercel에 배포된 정적 페이지 + 서버리스 함수 구조.

## 핵심 제약 (확정 사항)

- **OpenRouter**: `GET /api/v1/credits`로 충전액·사용액을 API 키로 직접 조회 가능 → 정확한 잔여 크레딧 계산.
- **OpenAI**: 일반 키로는 계정 사용량/비용 조회 불가. **Admin 키(`sk-admin-…`)** 로 Costs API(`/v1/organization/costs`)를 호출해 누적 사용 비용을 가져온다. 사용자가 입력한 **기준 잔액**에서 이 비용을 빼서 추정 잔액을 표시한다. ("남은 잔액" 직접 조회 API는 존재하지 않으므로 추정 방식이 유일.)
- **보안**: API 키는 코드/페이지에 두지 않고 **Vercel 환경변수**에 저장, 서버리스 함수만 접근한다. 브라우저로 키가 내려가지 않는다.

## 구조

```
apikey-balance.html      프론트엔드 (카드 2개)
api/openrouter.js        서버리스: OpenRouter 크레딧 조회
api/openai-cost.js       서버리스: OpenAI 누적 사용 비용 조회
```

### 환경변수 (Vercel)
- `OPENROUTER_API_KEY`
- `OPENAI_ADMIN_KEY`

## 동작

### OpenRouter (정확한 잔여량)
1. 프론트가 `/api/openrouter` 호출.
2. 함수가 `GET https://openrouter.ai/api/v1/credits` 호출 (`Authorization: Bearer $OPENROUTER_API_KEY`).
3. 응답 `data.total_credits`, `data.total_usage` 반환.
4. 프론트: **남은 크레딧 = total_credits − total_usage**.

### OpenAI (추정 잔여량)
1. 사용자가 OpenAI 카드에서 **기준 잔액($)** 과 **기준 날짜**를 입력 → `localStorage`에 저장.
2. 프론트가 `/api/openai-cost?start_time=<기준날짜 unix>` 호출.
3. 함수가 `GET https://api.openai.com/v1/organization/costs?start_time=<unix>` 호출 (`Authorization: Bearer $OPENAI_ADMIN_KEY`). 페이지네이션(`next_page`)이 있으면 모두 순회.
4. 일별 버킷의 `results[].amount.value` 합산 → 총 사용 비용(USD) 반환.
5. 프론트: **추정 잔액 = 기준 잔액 − 누적 사용 비용**.

## 화면

- 카드 2개(OpenRouter / OpenAI). 각 카드:
  - 큰 숫자로 남은 금액 표시, 사용량/총액 보조 표기.
  - 진행 바로 사용 비율 시각화.
- OpenAI 카드: 기준 잔액·기준 날짜 입력 + 저장 버튼.
- 상단: 전체 "새로고침" 버튼, 마지막 갱신 시각.
- 에러 시 카드에 사유 표시(키 미설정, 401/403, 네트워크 등).

## 에러 처리

- 함수: 환경변수 미설정 → 500 + 명확한 메시지. 상류 API 에러는 상태코드·본문을 그대로 전달.
- 프론트: 함수 응답이 에러면 해당 카드에 빨간 메시지, 숫자는 `—` 표시.

## 라우팅

- 기존 `vercel.json`의 `/` → `worldcup2026.html` 리라이트는 **건드리지 않는다.**
- 새 페이지는 `/apikey-balance.html` 경로로 접근.

## 테스트

- 서버리스 함수: OpenRouter/OpenAI 응답 형태에 대한 합산 로직 단위 테스트(목 응답).
- 완료 후 Playwright로 페이지 로드·렌더링 스모크 테스트.

## 범위 밖 (YAGNI)

- 키를 페이지에서 입력받는 기능(서버 env 사용).
- 다중 사용자/인증.
- 과거 추이 그래프.
