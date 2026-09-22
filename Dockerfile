# 필수 조건 2 — 채점자가 `docker compose up` 한 줄로 띄울 수 있어야 합니다.
FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/

# backend가 MCP 서버를 서브프로세스로 띄우고(services/llm.py) SKILL.md를 읽어야 하므로
# 같이 복사한다. data/ 는 복사하지 않는다 — 시뮬레이션 데이터는 저장소에 커밋하지 않고
# 외부 Postgres에서 읽는다 (MESTORY_DATA_SOURCE=db, docker-compose.yml에서 지정).
COPY mcp_server/ ./mcp_server/
COPY skills/ ./skills/

EXPOSE 8000
# Railway 등 PaaS는 컨테이너가 들을 포트를 PORT 환경변수로 알려준다.
# docker-compose는 PORT를 안 주므로 기본값 8000으로 그대로 동작한다.
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
