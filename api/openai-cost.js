export default async function handler(req, res) {
  // 환경변수 확인
  const adminKey = process.env.OPENAI_ADMIN_KEY;
  if (!adminKey) {
    return res.status(500).json({ error: 'OPENAI_ADMIN_KEY 환경변수가 설정되지 않았습니다.' });
  }

  // start_time 쿼리 파라미터 확인
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

    // 오류 응답 처리
    if (!response.ok) {
      const text = await response.text();
      return res.status(response.status).json({ error: text });
    }

    const page = await response.json();

    // 각 버킷의 비용 합산
    for (const bucket of page.data) {
      for (const result of bucket.results) {
        totalCost += result.amount.value;
      }
    }

    // 다음 페이지 URL 설정 (없으면 null로 루프 종료)
    url = page.has_more && page.next_page
      ? `https://api.openai.com/v1/organization/costs?start_time=${startTime}&limit=30&page=${page.next_page}`
      : null;
  }

  res.status(200).json({ total_cost: totalCost });
}
