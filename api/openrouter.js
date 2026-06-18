export default async function handler(req, res) {
  // 환경변수 확인
  const apiKey = process.env.OPENROUTER_API_KEY;
  if (!apiKey) {
    return res.status(500).json({ error: 'OPENROUTER_API_KEY 환경변수가 설정되지 않았습니다.' });
  }

  // OpenRouter 크레딧 조회 API 호출
  const response = await fetch('https://openrouter.ai/api/v1/credits', {
    headers: { Authorization: `Bearer ${apiKey}` },
  });

  // 오류 응답 처리
  if (!response.ok) {
    const text = await response.text();
    return res.status(response.status).json({ error: text });
  }

  // 정상 응답: total_credits, total_usage 반환
  const { data } = await response.json();
  res.status(200).json({ total_credits: data.total_credits, total_usage: data.total_usage });
}
