"""ZDR + tool calling 이 실제로 되는지 확인하는 일회용 진단 스크립트.

왜 llm.py를 안 거치나:
  llm.py는 실패를 3단계 폴백으로 삼켜서 "자동 분석 실패"만 남긴다.
  원인을 보려면 OpenRouter가 돌려준 응답 본문을 그대로 봐야 한다.
  그래서 SDK도 안 쓰고 httpx로 직접 POST한다 (SDK는 에러를 예외로 감싼다).

쓰는 법 (저장소 루트에서):
  python scripts/check_zdr.py                       # .env 의 OPENROUTER_API_KEY 사용
  python scripts/check_zdr.py --key sk-or-...       # 다른 키로
  python scripts/check_zdr.py --model openai/gpt-5-mini

모델을 바꾸기 전에 이걸 먼저 돌려서, 그 모델이 tools와 ZDR을 동시에
만족하는지 확인할 것. 둘 중 하나라도 안 되면 서비스가 폴백으로만 돈다.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import httpx
from dotenv import load_dotenv
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

BASE = "https://openrouter.ai/api/v1"

# 아무 도구나 하나. 중요한 건 "tools를 보냈다"는 사실이다 —
# tools가 있으면 OpenRouter가 tool calling 지원 엔드포인트로만 라우팅하므로,
# ZDR 필터와 겹쳐 후보가 0개가 되는지를 여기서 확인할 수 있다.
TOOLS = [{
    "type": "function",
    "function": {
        "name": "get_downtime",
        "description": "설비 정지 기록을 조회한다",
        "parameters": {
            "type": "object",
            "properties": {"equipment_id": {"type": "string"}},
            "required": ["equipment_id"],
        },
    },
}]


def mask(k: str) -> str:
    return f"{k[:10]}...{k[-4:]}" if len(k) > 16 else "****"


def probe(client: httpx.Client, key: str, model: str, *, with_tools: bool, zdr: bool | None):
    body: dict = {
        "model": model,
        "messages": [{"role": "user", "content": "EQ-001 정지 원인 알려줘"}],
        "max_tokens": 256,
    }
    if with_tools:
        body["tools"] = TOOLS
    if zdr is not None:
        body["provider"] = {"zdr": zdr}

    label = f"tools={'O' if with_tools else 'X'}  provider.zdr={zdr if zdr is not None else '미지정'}"
    try:
        r = client.post(
            f"{BASE}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=body,
            timeout=60,
        )
    except Exception as exc:
        print(f"  [{label}]  ❌ 연결 실패: {exc!r}")
        return

    if r.status_code == 200:
        d = r.json()
        # OpenRouter는 어느 provider가 처리했는지 응답에 넣어준다 — 이게 핵심 증거다.
        served = d.get("provider") or "(provider 필드 없음)"
        msg = (d.get("choices") or [{}])[0].get("message", {})
        did_tool = bool(msg.get("tool_calls"))
        print(f"  [{label}]  ✅ 200  provider={served}  도구호출={'O' if did_tool else 'X'}")
    else:
        print(f"  [{label}]  ❌ {r.status_code}")
        try:
            print("      " + json.dumps(r.json(), ensure_ascii=False)[:600])
        except Exception:
            print("      " + r.text[:600])


def endpoints(client: httpx.Client, key: str, model: str):
    """이 모델을 어느 엔드포인트들이 서비스하는지. tools 지원 여부가 같이 나온다."""
    try:
        r = client.get(f"{BASE}/models/{model}/endpoints",
                       headers={"Authorization": f"Bearer {key}"}, timeout=30)
    except Exception as exc:
        print(f"  조회 실패: {exc!r}")
        return
    if r.status_code != 200:
        print(f"  조회 실패 {r.status_code}: {r.text[:300]}")
        return
    eps = (r.json().get("data") or {}).get("endpoints") or []
    if not eps:
        print("  엔드포인트 정보 없음")
        return
    print(f"  {'provider':28} {'tools':6} {'컨텍스트':>8}")
    for e in eps:
        params = e.get("supported_parameters") or []
        print(f"  {str(e.get('provider_name'))[:28]:28} "
              f"{'O' if 'tools' in params else 'X':6} "
              f"{str(e.get('context_length') or '-'):>8}")


def probe_like_app(client: httpx.Client, key: str, model: str):
    """llm.py가 실제로 보내는 것과 같은 요청.

    앞의 네 조합은 tools/zdr만 봤다. 실제 요청에는 temperature=0,
    max_tokens=2000, reasoning 이 더 붙는다 — 추론 모델은 temperature를
    거부하기도 하고, 추론 토큰이 max_tokens를 먼저 써서 답이 잘리기도 한다.
    측정을 돌리기 전에 여기서 걸러낸다.
    """
    body = {
        "model": model,
        "messages": [{"role": "user", "content": "EQ-001의 2026-08-10 정지 원인을 조회해서 알려줘"}],
        "tools": TOOLS,
        "temperature": 0,                       # llm.py와 동일
        "max_tokens": 2000,                     # MAX_OUTPUT_TOKENS
        "provider": {"zdr": True},
        "reasoning": {"effort": "low", "exclude": True},
    }
    r = client.post(f"{BASE}/chat/completions",
                    headers={"Authorization": f"Bearer {key}"}, json=body, timeout=90)
    if r.status_code != 200:
        print(f"  ❌ {r.status_code}")
        print("     " + r.text[:600])
        return

    d = r.json()
    ch = (d.get("choices") or [{}])[0]
    msg = ch.get("message", {})
    usage = d.get("usage") or {}
    reasoning_tok = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")

    print(f"  ✅ 200  provider={d.get('provider')}")
    print(f"     도구호출   : {'O' if msg.get('tool_calls') else 'X'}")
    print(f"     finish     : {ch.get('finish_reason')}   ← length 면 max_tokens에 잘린 것")
    print(f"     출력 토큰  : {usage.get('completion_tokens')} "
          f"(그중 추론 {reasoning_tok if reasoning_tok is not None else '?'})")
    if ch.get("finish_reason") == "length":
        print("     ⚠️ 잘렸다 — MAX_OUTPUT_TOKENS를 올리거나 reasoning effort를 낮춰야 한다")


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", default=None)
    ap.add_argument("--model", default=os.getenv("MESTORY_LLM_MODEL", "openai/gpt-4o-mini"))
    args = ap.parse_args()

    key = args.key or os.getenv("OPENROUTER_API_KEY")
    if not key:
        print("키가 없습니다. .env의 OPENROUTER_API_KEY 또는 --key 로 주세요.")
        return 1

    print(f"모델 : {args.model}")
    print(f"키   : {mask(key)}")

    with httpx.Client() as client:
        print("\n── 이 모델을 서비스하는 엔드포인트 ──")
        endpoints(client, key, args.model)

        print("\n── 네 가지 조합으로 실제 호출 ──")
        for with_tools in (False, True):
            for zdr in (None, True):
                probe(client, key, args.model, with_tools=with_tools, zdr=zdr)

        print("\n── 우리 서비스와 똑같은 요청 (이게 되어야 실제로 동작한다) ──")
        probe_like_app(client, key, args.model)

    print("\n읽는 법:")
    print("  tools=O 인 줄만 200이면  → 우리 서비스는 정상 동작한다")
    print("  tools=O 에서만 실패하면  → tool calling 지원 엔드포인트가 ZDR에서 빠진 것")
    print("  zdr=True 에서만 성공하면 → 요청에 provider 옵션을 붙여야 한다는 뜻")
    return 0


if __name__ == "__main__":
    sys.exit(main())
