"""리포트 메일 발송 (docs/specs/report-email.md).

이 파일은 "메일을 만들고 보내는 일"만 한다. HTTP 라우팅은 main.py가 맡는다.
나눠 둔 이유: 시험에서 실제 메일을 보내지 않고 이 함수들만 가짜로 바꿔 끼우기 위해서다.
"""

from __future__ import annotations

import os
from html import escape
from typing import Any

# 환경변수 이름을 상수로 둔다 — 오타가 나면 조용히 "설정 없음"으로 동작해 버리기 때문이다.
ALLOWLIST_ENV = "REPORT_EMAIL_ALLOWLIST"


def _normalize(address: str) -> str:
    """메일 주소를 비교하기 좋은 형태로 다듬는다 (앞뒤 공백 제거 + 소문자).

    소문자로 맞추는 이유: 메일 주소는 대소문자를 구분하지 않는 것이 관례다.
    'A@x.com'과 'a@x.com'은 같은 사람인데, 그냥 비교하면 다른 값이 된다.
    """
    return (address or "").strip().lower()


def is_allowed_recipient(to: str) -> bool:
    """이 주소로 메일을 보내도 되는지 판단한다.

    허용 목록은 REPORT_EMAIL_ALLOWLIST 환경변수에 쉼표로 구분해 적는다.
        REPORT_EMAIL_ALLOWLIST=a@example.com, b@example.com

    ⚠️ 목록이 없거나 비어 있으면 **모두 거절한다** (Spec AC-05).
    흔한 실수가 "설정이 없으면 일단 통과"로 짜는 것인데, 그러면 .env를 하나 빠뜨렸을 때
    조용히 아무에게나 메일이 나간다. 기본값은 안전한 쪽(막힘)이어야 한다.
    """
    raw = os.getenv(ALLOWLIST_ENV, "")

    # 쉼표로 자른 뒤 각 항목을 다듬고, 빈 항목은 버린다.
    # "a@x.com,,b@y.com"이나 끝에 쉼표가 붙은 값도 이 단계에서 정리된다.
    allowed = {_normalize(item) for item in raw.split(",") if item.strip()}

    if not allowed:
        return False

    # 입력 주소도 목록과 똑같은 방식으로 다듬어야 한다.
    # 한쪽만 소문자로 바꾸면 'A@x.com'이 목록에 있어도 막힌다.
    return _normalize(to) in allowed


# ─────────────────────────────────────────────
# (2) 메일 본문 만들기
#
# 새 라이브러리(Jinja2 등)를 쓰지 않고 파이썬 문자열로 만든다 — 의존성을 늘리지 않는 팀 방식.
# 메일 본문은 화면과 달리 한 번 만들고 끝이라, 템플릿 엔진의 이점이 크지 않다.
# ─────────────────────────────────────────────

def _esc(value: Any) -> str:
    """HTML에 넣어도 안전한 글자로 바꾼다.

    왜 필요한가:
      HTML은 '<'를 "태그 시작" 신호로 읽는다. 리포트 값에 그 글자가 있으면
      글자가 아니라 명령으로 해석돼 내용이 통째로 사라지거나 표가 깨진다.
        "전류 <정격 30A> 초과"  →  화면에는 "전류  초과"만 남는다
      LLM이 쓴 문장이라 <, >, & 가 언제든 들어올 수 있다.
      값에 <script>가 들어가면 메일 앱에 따라 실행될 수도 있다(XSS).

    quote=True로 따옴표까지 바꾸는 이유:
      href="..." 같은 속성 안에 값을 넣을 때, 값 속의 따옴표가 속성을 먼저 닫아버리기 때문이다.
    """
    if value is None:
        return ""
    return escape(str(value), quote=True)


def _esc_multiline(value: Any) -> str:
    """여러 줄 글을 HTML에서도 줄이 나뉘게 만든다.

    HTML은 줄바꿈 문자를 공백 한 칸으로 취급한다. 그냥 넣으면 권장 조치 여러 항목이
    한 덩어리로 붙어 버린다(llm.py가 항목마다 줄바꿈을 넣어 보내는데 그게 무시된다).
    먼저 escape한 뒤에 <br>로 바꾼다 — 순서가 반대면 방금 넣은 <br>까지 글자가 된다.
    """
    return _esc(value).replace("\n", "<br>")


def _severity_color(severity: str) -> str:
    """심각도에 따른 배지 색. 메일에서는 CSS 파일을 못 쓰므로 style 속성에 직접 적는다."""
    return {
        "중대": "#d64545",
        "보통": "#d98324",
        "경미": "#2f9e6e",
        "판정 불가": "#8b93a3",
    }.get(severity, "#8b93a3")


def _report_url(report: dict, base_url: str) -> str:
    """메일에서 원본 화면으로 돌아오는 링크. 끝 슬래시가 겹치지 않게 정리한다."""
    return f"{(base_url or '').rstrip('/')}/reports/{report.get('id', '')}"


def render_report_email(report: dict, base_url: str) -> tuple[str, str]:
    """리포트 dict 하나를 (HTML 본문, 텍스트 본문) 두 벌로 만든다.

    왜 두 벌인가:
      메일 앱 중에는 HTML을 안 보여 주거나 사용자가 꺼 둔 경우가 있다.
      그때 보여줄 대체본이 없으면 빈 메일로 보인다. 같은 내용을 줄글로도 함께 보낸다.
    """
    equipment = report.get("equipment_id") or "전체 설비"
    line = report.get("line_id") or "전체 라인"
    period = report.get("period") or "-"
    causes = report.get("causes") or []
    unclassified = report.get("unclassified_count") or 0
    link = _report_url(report, base_url)

    # ── HTML 본문 ──
    # 메일 앱은 외부 CSS나 <style> 태그를 자주 무시한다. 그래서 style을 태그마다 직접 적는다.
    rows = []
    for cause in causes:
        severity = cause.get("severity") or "판정 불가"
        rows.append(
            '<tr>'
            f'<td style="padding:10px 12px;border-bottom:1px solid #eceef3;font-weight:700;white-space:nowrap">{_esc(cause.get("error_code"))}</td>'
            f'<td style="padding:10px 12px;border-bottom:1px solid #eceef3">{_esc_multiline(cause.get("description"))}</td>'
            f'<td style="padding:10px 12px;border-bottom:1px solid #eceef3;white-space:nowrap">'
            f'<span style="background:{_severity_color(severity)};color:#fff;border-radius:99px;padding:3px 10px;font-size:12px">{_esc(severity)}</span>'
            '</td>'
            f'<td style="padding:10px 12px;border-bottom:1px solid #eceef3;color:#5b667c;font-size:13px">{_esc_multiline(cause.get("evidence"))}</td>'
            '</tr>'
        )
    rows_html = "".join(rows) or (
        '<tr><td colspan="4" style="padding:16px;color:#8b93a3">확인된 원인이 없습니다.</td></tr>'
    )

    html_body = f"""<!DOCTYPE html>
<html lang="ko"><body style="margin:0;padding:24px;background:#f5f6fa;font-family:'Malgun Gothic','Apple SD Gothic Neo',sans-serif;color:#2d3a5a">
  <div style="max-width:760px;margin:0 auto;background:#fff;border-radius:14px;padding:28px 30px">
    <h1 style="margin:0 0 6px;font-size:20px">설비 정지 원인 분석 리포트</h1>
    <p style="margin:0 0 20px;color:#5b667c;font-size:14px">
      설비 <strong>{_esc(equipment)}</strong> · 라인 <strong>{_esc(line)}</strong> · 기간 {_esc(period)}
    </p>

    <h2 style="font-size:15px;margin:24px 0 10px">원인 {len(causes)}건{f' · 확인 필요 {unclassified}건' if unclassified else ''}</h2>
    <table style="width:100%;border-collapse:collapse;font-size:14px">
      <thead><tr style="background:#f7f8fc">
        <th style="text-align:left;padding:10px 12px;font-size:12px;color:#5b667c">에러코드</th>
        <th style="text-align:left;padding:10px 12px;font-size:12px;color:#5b667c">설명</th>
        <th style="text-align:left;padding:10px 12px;font-size:12px;color:#5b667c">심각도</th>
        <th style="text-align:left;padding:10px 12px;font-size:12px;color:#5b667c">판단 근거</th>
      </tr></thead>
      <tbody>{rows_html}</tbody>
    </table>

    <h2 style="font-size:15px;margin:26px 0 8px">권장 조치</h2>
    <div style="background:#f3f1ff;border-radius:10px;padding:14px 16px;font-size:14px;line-height:1.7">{_esc_multiline(report.get("recommended_action")) or "-"}</div>

    <h2 style="font-size:15px;margin:22px 0 8px">분석 참고 사항</h2>
    <div style="background:#eef4ff;border-radius:10px;padding:14px 16px;font-size:14px;line-height:1.7">{_esc_multiline(report.get("confidence_note")) or "-"}</div>

    <p style="margin:26px 0 0">
      <a href="{_esc(link)}" style="display:inline-block;background:#6b5ce7;color:#fff;text-decoration:none;border-radius:9px;padding:11px 20px;font-weight:700;font-size:14px">전체 리포트 보기</a>
    </p>
    <p style="margin:12px 0 0;color:#8b93a3;font-size:12px">최종 원인 확정과 조치 실행은 담당자가 현장을 확인한 뒤 결정합니다.</p>
  </div>
</body></html>"""

    # ── 텍스트 대체본 ──
    # 여기서는 escape를 하지 않는다. HTML이 아니라 그냥 글이라 <가 명령으로 읽히지 않는다.
    lines = [
        "설비 정지 원인 분석 리포트",
        "",
        f"설비: {equipment}",
        f"라인: {line}",
        f"기간: {period}",
        "",
        f"[원인 {len(causes)}건" + (f" · 확인 필요 {unclassified}건]" if unclassified else "]"),
    ]
    if causes:
        for index, cause in enumerate(causes, start=1):
            lines.append(f"{index}. {cause.get('error_code') or '(코드 없음)'} — {cause.get('severity') or '판정 불가'}")
            if cause.get("description"):
                lines.append(f"   설명: {cause['description']}")
            if cause.get("evidence"):
                lines.append(f"   근거: {cause['evidence']}")
    else:
        lines.append("확인된 원인이 없습니다.")

    lines += [
        "",
        "[권장 조치]",
        str(report.get("recommended_action") or "-"),
        "",
        "[분석 참고 사항]",
        str(report.get("confidence_note") or "-"),
        "",
        f"전체 리포트 보기: {link}",
        "",
        "최종 원인 확정과 조치 실행은 담당자가 현장을 확인한 뒤 결정합니다.",
    ]
    text_body = "\n".join(lines)

    return html_body, text_body
