# backend — 진행상황

## 상태

- [X]  `/health` 엔드포인트 (스캐폴딩 기본 제공)
- [ ]  도메인 엔드포인트 설계 및 구현
- [ ]  요청/응답 Pydantic 모델 정의 (필수 3 — 출력 계약)
- [ ]  `services/llm.py` — LLM 호출 단일 창구 구현
  - [ ]  출력 계약 검증 (Pydantic)
  - [ ]  실패 시 재시도 / 폴백
  - [ ]  Langfuse 트레이스
- [ ]  구조화 로그 (요청 ID · 사용 모델 · 토큰 수 · 지연 시간)

## 실행 방법

```bash
cp .env.example .env   # 키 채우기
docker compose up
curl http://localhost:8000/health
```

## TODO / 막힌 것

(진행하면서 여기에 채워주세요)
