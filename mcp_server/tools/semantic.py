"""
보조 창구 ④: 유사 문장 검색 (시맨틱-lite)  (팀 PRD 확장)

누가 부르나
  - LangChain 에이전트(AI)가 "정확히 같은 단어가 없어도 뜻이 비슷한 기록"을
    찾고 싶을 때 부른다. exact 조회(창구 ①②③)가 0건이거나, 표현이 달라서
    놓친 기록이 있을 때의 보조 수단이다.

하는 일
  - 정지 로그의 operator_note / 정비이력의 action_taken+result /
    에러코드 사전의 description+typical_cause 를 문장 유사도로 순위 매겨 돌려준다.
  - 점수(score)와 원문·ID(LOG-/MT-/에러코드)를 항상 함께 돌려준다.
    → 점수 없이 문장만 주면 에이전트가 근거를 인용할 수 없고,
       id_grounding 채점도 할 수 없기 때문이다.

하지 않는 일 (안전선)
  - 에러코드·설비ID·라인ID의 동일성 판단. ID는 항상 exact 조회(창구 ①②③)가 정한다.
    여기서는 설명문(descripton 등)만 검색하고, 코드를 "찾아주는" 일은 하지 않는다.
  - 원인 확정·심각도 판정. 결과는 후보일 뿐이며, needs_review=true 면
    에이전트는 단정하지 말고 사람 확인을 요청해야 한다.
  - dedup(원인 중복 제거). 그건 backend/services/llm.py의 어휘 기반 후처리 담당이다.

왜 TF-IDF가 기본인가
  - sentence-transformers 같은 임베딩 모델은 외부 다운로드·GPU·비용이 들고,
    ZDR(외부 전송 금지) 정책과도 충돌할 수 있다. 이 프로젝트의 평가는
    오프라인·재현 가능해야 하므로, 기본 백엔드는 sklearn TF-IDF(문자 n-gram)로 둔다.
  - 한국어 형태소 분석기 없이도 동작하도록 analyzer="char_wb"를 쓴다.
    짧은 기술 메모("베어링 소음"↔"베어링 진동")는 글자가 많이 겹치므로,
    threshold를 낮게 잡으면 서로 다른 원인을 묶는 오탐이 난다.
    그래서 기본 threshold를 보수적으로 두고, needs_review로 모호함을 알린다.
  - 진짜 임베딩이 필요해지면 MESTORY_SEMANTIC_BACKEND=sbert 로 바꾼다.
    그때는 모델을 명시적으로 불러오고, 실패하면 조용히 TF-IDF로 떨어지지 않고
    에러를 낸다 — "시맨틱이라면서 실은 글자 비교"인 상태를 숨기지 않기 위해서다.
"""

from __future__ import annotations

import os

# ─────────────────────────────────────────────
# 설정값 (바꿀 일이 생기면 여기만 고친다)
# ─────────────────────────────────────────────
# TF-IDF 문자 n-gram 범위. 한국어 조사·어미가 달라도 핵심어 글자가 겹치면 잡히고,
# 형태소 분석기가 필요 없다. (2,3)이 짧은 메모에 가장 안정적이라는 실측 기준.
NGRAM_RANGE = (2, 3)

# 기본 임계값. char n-gram 코사인 유사도 기준이다.
# 실측 기준: 같은 핵심어 1개 공유 시 0.2~0.6, 무관 문장 0.0~0.1.
# 0.12 미만은 "우연히 글자가 겹친 수준"으로 보고 버린다.
DEFAULT_THRESHOLD = 0.12

# 모호함 판정 기준. 1위와 2위 점수 차가 이 값보다 작고 1위가 0.5 미만이면
# "어느 쪽인지 가리기 어렵다"로 보고 needs_review=true.
AMBIGUITY_GAP = 0.03
AMBIGUITY_CEILING = 0.5

# 한 번에 돌려줄 최대 후보 수. 기록 한 줄이 길지 않지만, LLM 프롬프트에
# 그대로 들어가므로 상한을 둔다 (창구 ①의 limit 철학과 같음).
MAX_TOP_K = 20

# ⚠️ 후보를 날짜순 head()로 자르지 않는다. 앞에서만 자르면 오래된 기록만
# 검색돼 결과가 조용히 편향된다. 14,099행 전체 TF-IDF 벡터화는 0.1초 이내라
# 자를 이유가 없다. 데이터가 수십만 행을 넘으면 그때 FAISS 같은 인덱스로 교체한다.

# sbert 백엔드 기본 모델. 다국어(한국어 포함) 경량 모델이다.
# 바꾸려면 환경변수 MESTORY_SEMANTIC_MODEL 로 지정한다.
DEFAULT_SBERT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def get_backend_name() -> str:
    """쓸 백엔드 이름. tfidf(기본) 또는 sbert. 환경변수로 바꾼다."""
    name = os.getenv("MESTORY_SEMANTIC_BACKEND", "tfidf").strip().lower()
    if name not in ("tfidf", "sbert"):
        raise RuntimeError(
            f"MESTORY_SEMANTIC_BACKEND 값이 잘못됐습니다: '{name}' (tfidf 또는 sbert만 가능)"
        )
    return name


# ─────────────────────────────────────────────
# 유사도 계산 (백엔드별)
# ─────────────────────────────────────────────
def _tfidf_vectorizer():
    from sklearn.feature_extraction.text import TfidfVectorizer

    return TfidfVectorizer(analyzer="char_wb", ngram_range=NGRAM_RANGE, min_df=1)


def _build_tfidf_index(texts: list[str]):
    vectorizer = _tfidf_vectorizer()
    matrix = vectorizer.fit_transform(texts)
    return vectorizer, matrix


def _sbert_model():
    """sbert 모델을 늦게 불러온다. 설치·다운로드 실패는 숨기지 않고 알린다."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            "MESTORY_SEMANTIC_BACKEND=sbert 인데 sentence-transformers가 설치돼 있지 않습니다. "
            "pip install sentence-transformers 로 설치하거나, 기본값(tfidf)으로 돌리세요."
        ) from exc
    model_name = os.getenv("MESTORY_SEMANTIC_MODEL", DEFAULT_SBERT_MODEL)
    return SentenceTransformer(model_name)


def _rank_texts(
    query: str,
    texts: list[str],
    *,
    top_k: int,
    threshold: float,
    backend: str,
) -> list[tuple[int, float]]:
    """질의와 문서들의 유사도를 재서 (문서번호, 점수) 목록을 점수 순으로 돌려준다.

    threshold 미만은 버린다. 점수는 코사인 유사도(0.0~1.0)다.
    """
    if backend == "sbert":
        import numpy as np

        model = _sbert_model()
        doc_emb = model.encode(texts, normalize_embeddings=True)
        q_emb = model.encode([query], normalize_embeddings=True)[0]
        scores = (doc_emb @ q_emb).tolist()
    else:
        vectorizer, matrix = _build_tfidf_index(texts)
        q_vec = vectorizer.transform([query])
        # TF-IDF 벡터는 기본 L2 정규화라 내적 = 코사인 유사도다.
        scores = (matrix * q_vec.T).toarray().ravel().tolist()

    ranked = sorted(
        ((i, float(s)) for i, s in enumerate(scores) if float(s) >= threshold),
        key=lambda pair: (-pair[1], pair[0]),  # 점수 내림차순, 동점이면 원래 순서
    )
    return ranked[:top_k]


def _needs_review(scores: list[float], threshold: float) -> tuple[bool, str]:
    """결과가 단정하기에 불안한지 판단한다. (05강 resolve_semantic 패턴)

    - 0건 → True ("못 찾음"을 "없음"으로 단정 금지)
    - 1위가 threshold 근처 → True (우연한 글자 겹침 수준)
    - 1·2위 차이가 미세하고 1위가 낮음 → True (어느 쪽인지 모름)
    """
    if not scores:
        return True, "임계값 이상의 후보가 없습니다. exact 조회로 조건을 넓혀 다시 보세요."
    top = scores[0]
    if top < threshold + 0.1:
        return True, f"최고 점수({top:.3f})가 임계값({threshold}) 근처입니다. 후보를 참고만 하세요."
    if len(scores) >= 2 and (scores[0] - scores[1]) < AMBIGUITY_GAP and top < AMBIGUITY_CEILING:
        return True, "1·2위 점수 차이가 미세합니다. 어느 쪽인지 단정하지 마세요."
    return False, ""


def _finalize(
    *,
    query: str,
    backend: str,
    threshold: float,
    top_k: int,
    total_candidates: int,
    hits: list[dict],
) -> dict:
    scores = [h["score"] for h in hits]
    needs_review, review_reason = _needs_review(scores, threshold)
    return {
        "query": query,
        "backend": backend,  # "tfidf"면 글자 기반, "sbert"면 임베딩 기반 — 숨기지 않는다
        "threshold": threshold,
        "top_k": top_k,
        "total_candidates": total_candidates,  # exact 필터 뒤 유사도를 잰 행 수
        "returned_count": len(hits),
        "needs_review": needs_review,
        "review_reason": review_reason,
        "results": hits,
    }


def _check_args(query: str, top_k: int, threshold: float) -> int:
    if not (query or "").strip():
        raise ValueError("검색 문장(query)을 넣어 주세요.")
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold는 0.0~1.0 사이여야 합니다.")
    return max(1, min(int(top_k), MAX_TOP_K))


# ─────────────────────────────────────────────
# 1. 정지 로그 operator_note 검색
# ─────────────────────────────────────────────
def search_operator_notes(
    query: str,
    top_k: int = 5,
    threshold: float = DEFAULT_THRESHOLD,
    equipment_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    """정지 로그의 작업자 메모(operator_note)에서 질의와 비슷한 기록을 찾는다.

    equipment_id·date_from·date_to는 exact 필터다(창구 ①과 같은 규칙).
    메모가 비어 있는 행은 후보에서 뺀다.
    """
    from .data_loader import load_downtime_logs
    from .downtime import _normalize_id, _parse_date

    top_k = _check_args(query, top_k, threshold)
    backend = get_backend_name()

    equipment_id = _normalize_id(equipment_id) if equipment_id else None
    start = _parse_date(date_from, "date_from") if date_from else None
    end = _parse_date(date_to, "date_to") if date_to else None
    if start and end and start > end:
        raise ValueError(f"date_from({date_from})이 date_to({date_to})보다 늦습니다.")

    df = load_downtime_logs()
    mask = df["operator_note"].str.strip() != ""
    if equipment_id:
        mask &= df["equipment_id"] == equipment_id
    if start:
        mask &= df["_start_dt"].dt.date >= start
    if end:
        mask &= df["_start_dt"].dt.date <= end

    matched = df[mask].sort_values("_start_dt", kind="stable")
    texts = matched["operator_note"].str.strip().tolist()
    total = len(matched)
    if not texts:
        return _finalize(
            query=query, backend=backend, threshold=threshold, top_k=top_k,
            total_candidates=0, hits=[],
        )

    ranked = _rank_texts(query.strip(), texts, top_k=top_k, threshold=threshold, backend=backend)
    rows = matched.to_dict("records")
    hits = [
        {
            "score": round(score, 4),
            "log_id": rows[i]["log_id"],
            "equipment_id": rows[i]["equipment_id"],
            "error_code": rows[i]["error_code"],
            "start_time": rows[i]["start_time"],
            "operator_note": rows[i]["operator_note"],
        }
        for i, score in ranked
    ]
    return _finalize(
        query=query, backend=backend, threshold=threshold, top_k=top_k,
        total_candidates=total, hits=hits,
    )


# ─────────────────────────────────────────────
# 2. 정비이력 action_taken+result 검색
# ─────────────────────────────────────────────
def search_maintenance_actions(
    query: str,
    top_k: int = 5,
    threshold: float = DEFAULT_THRESHOLD,
    equipment_id: str | None = None,
) -> dict:
    """정비이력의 조치 내용(action_taken + result)에서 비슷한 과거 조치를 찾는다.

    "같은 증상을 과거에 어떻게 고쳤나"를 볼 때 쓴다. 원인 확정 근거로 쓰지 않는다.
    equipment_id를 주면 그 설비로 exact 필터한다.
    """
    from .data_loader import load_maintenance
    from .downtime import _normalize_id

    top_k = _check_args(query, top_k, threshold)
    backend = get_backend_name()

    equipment_id = _normalize_id(equipment_id) if equipment_id else None

    df = load_maintenance()
    df = df.copy()
    df["_text"] = (df["action_taken"].str.strip() + " / " + df["result"].str.strip()).str.strip(" /")
    mask = df["_text"].str.strip() != ""
    if equipment_id:
        mask &= df["equipment_id"] == equipment_id

    matched = df[mask].sort_values(["date", "maintenance_id"], kind="stable")
    texts = matched["_text"].tolist()
    total = len(matched)
    if not texts:
        return _finalize(
            query=query, backend=backend, threshold=threshold, top_k=top_k,
            total_candidates=0, hits=[],
        )

    ranked = _rank_texts(query.strip(), texts, top_k=top_k, threshold=threshold, backend=backend)
    rows = matched.to_dict("records")
    hits = [
        {
            "score": round(score, 4),
            "maintenance_id": rows[i]["maintenance_id"],
            "equipment_id": rows[i]["equipment_id"],
            "date": rows[i]["date"],
            "action_taken": rows[i]["action_taken"],
            "result": rows[i]["result"],
        }
        for i, score in ranked
    ]
    return _finalize(
        query=query, backend=backend, threshold=threshold, top_k=top_k,
        total_candidates=total, hits=hits,
    )


# ─────────────────────────────────────────────
# 3. 에러코드 사전 설명문 검색
# ─────────────────────────────────────────────
def search_error_descriptions(
    query: str,
    top_k: int = 5,
    threshold: float = DEFAULT_THRESHOLD,
) -> dict:
    """에러코드 사전의 설명문(description + typical_cause + category)에서
    질의와 비슷한 항목을 찾는다.

    ⚠️ 결과는 "비슷한 설명 후보"일 뿐, 코드 판정이 아니다.
    코드ID의 동일성은 lookup_error_codes(exact)가 정한다.
    증상으로 코드를 추정해야 할 때(에이전트의 가설 세우기용)만 쓰고,
    최종 원인에는 exact 조회로 확인된 코드만 올린다.
    """
    from .data_loader import load_error_codes

    top_k = _check_args(query, top_k, threshold)
    backend = get_backend_name()

    df = load_error_codes()
    df = df.copy()
    df["_text"] = (
        df["description"].str.strip()
        + " / " + df["typical_cause"].str.strip()
        + " / " + df["category"].str.strip()
    ).str.strip(" /")
    matched = df[df["_text"].str.strip() != ""].sort_values("error_code", kind="stable")
    texts = matched["_text"].tolist()

    ranked = _rank_texts(query.strip(), texts, top_k=top_k, threshold=threshold, backend=backend)
    rows = matched.to_dict("records")
    hits = [
        {
            "score": round(score, 4),
            "error_code": rows[i]["error_code"],
            "category": rows[i]["category"],
            "description": rows[i]["description"],
            "typical_cause": rows[i]["typical_cause"],
        }
        for i, score in ranked
    ]
    return _finalize(
        query=query, backend=backend, threshold=threshold, top_k=top_k,
        total_candidates=len(matched), hits=hits,
    )
