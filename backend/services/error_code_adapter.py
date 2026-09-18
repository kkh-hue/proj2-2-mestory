"""기존 오류 코드 사전을 TOP3 표시용 공식 설명으로 변환한다."""

from mcp_server.tools.error_codes import lookup_error_codes


def get_official_descriptions(error_codes: list[str]) -> dict[str, str | None]:
    """사전에 등록된 코드의 description만 반환하며, LLM 문장을 만들지 않는다."""
    if not error_codes:
        return {}
    lookup = lookup_error_codes(error_codes)
    return {
        str(item["error_code"]): str(item["description"])
        if item.get("found") and item.get("description") else None
        for item in lookup["results"]
    }
