"""모델 라우팅 AC — docs/specs/model-routing.md

이미지 유무로 모델이 갈리는지만 본다. 실제 LLM/MCP 호출은 하지 않는다
(환경변수를 바꿔 가며 함수가 무엇을 돌려주는지 확인하는 수준).

여기서 확인하지 않는 AC (실제 API 키·측정이 필요해서 evals로 확인):
  AC-05 스키마 준수가 떨어지지 않는다  → scripts/score_multimodal.py
  AC-06 비용 비교표가 실측 토큰으로 나온다 → evals/EVAL_REPORT
"""

import pytest

from backend.services import llm as llm_module

# 이 파일의 시험은 CSV/DB 데이터가 없어도 돌아간다 (conftest.py의 no_data 표시).
pytestmark = pytest.mark.no_data


@pytest.fixture
def env(monkeypatch):
    """모델 관련 환경변수를 깨끗한 상태에서 시작하게 한다.

    왜 필요한가: .env가 이미 os.environ에 올라와 있어서, 지우지 않으면
    내 PC의 .env 값에 따라 시험 결과가 달라진다(= 남의 PC에서 깨진다).
    """
    monkeypatch.delenv("MESTORY_LLM_MODEL", raising=False)
    monkeypatch.delenv("MESTORY_LLM_MODEL_VISION", raising=False)
    return monkeypatch


# ─────────────────────────────────────────────
# AC-01 · 환경변수가 없으면 회귀가 없다
# ─────────────────────────────────────────────
def test_AC01_VISION이_없으면_이미지_유무와_무관하게_같은_모델(env):
    env.setenv("MESTORY_LLM_MODEL", "openai/gpt-5-mini")
    # MESTORY_LLM_MODEL_VISION은 설정하지 않은 상태 (env fixture가 지워 뒀다)

    assert llm_module.resolve_model_name(False) == "openai/gpt-5-mini"
    assert llm_module.resolve_model_name(True) == "openai/gpt-5-mini"


def test_AC01_둘_다_없으면_기존_기본값을_그대로_쓴다(env):
    # get_model_name()의 기본값과 어긋나면 안 된다 — 어긋나면 조용히 다른 모델로 간다
    assert llm_module.resolve_model_name(True) == llm_module.get_model_name()
    assert llm_module.resolve_model_name(False) == llm_module.get_model_name()


# ─────────────────────────────────────────────
# AC-02 · 이미지 유무로 모델이 갈린다
# ─────────────────────────────────────────────
def test_AC02_이미지_유무로_모델이_갈린다(env):
    env.setenv("MESTORY_LLM_MODEL", "openai/gpt-5-nano")
    env.setenv("MESTORY_LLM_MODEL_VISION", "openai/gpt-5-mini")

    assert llm_module.resolve_model_name(False) == "openai/gpt-5-nano"   # 텍스트 경로
    assert llm_module.resolve_model_name(True) == "openai/gpt-5-mini"    # 이미지 경로


# ─────────────────────────────────────────────
# AC-03 · 빈 값은 미설정과 같다
# ─────────────────────────────────────────────
@pytest.mark.parametrize("empty_value", ["", "   ", "\t"])
def test_AC03_VISION이_비어_있으면_미설정과_같다(env, empty_value):
    env.setenv("MESTORY_LLM_MODEL", "openai/gpt-5-nano")
    env.setenv("MESTORY_LLM_MODEL_VISION", empty_value)

    # .env에 키만 남기고 값을 지운 경우 — 빈 모델명으로 요청이 나가면 안 된다
    assert llm_module.resolve_model_name(True) == "openai/gpt-5-nano"


# ─────────────────────────────────────────────
# AC-04 · 라우팅된 모델이 실제 LLM 객체에 전달된다
# ─────────────────────────────────────────────
def test_AC04_라우팅된_모델명이_ChatOpenAI에_들어간다(env):
    env.setenv("MESTORY_LLM_MODEL", "openai/gpt-5-nano")
    env.setenv("MESTORY_LLM_MODEL_VISION", "openai/gpt-5-mini")
    env.setenv("OPENROUTER_API_KEY", "test-key")       # 키가 없으면 RuntimeError가 난다
    env.delenv("MESTORY_LLM_API_KEY", raising=False)

    text_llm = llm_module._build_llm(llm_module.resolve_model_name(False))
    vision_llm = llm_module._build_llm(llm_module.resolve_model_name(True))

    assert text_llm.model_name == "openai/gpt-5-nano"
    assert vision_llm.model_name == "openai/gpt-5-mini"


def test_AC04_인자를_안_주면_기존_동작_그대로(env):
    # _build_llm()을 인자 없이 부르던 기존 코드가 있어도 깨지지 않아야 한다
    env.setenv("MESTORY_LLM_MODEL", "openai/gpt-5-mini")
    env.setenv("MESTORY_LLM_MODEL_VISION", "openai/gpt-5-nano")
    env.setenv("OPENROUTER_API_KEY", "test-key")
    env.delenv("MESTORY_LLM_API_KEY", raising=False)

    assert llm_module._build_llm().model_name == "openai/gpt-5-mini"
