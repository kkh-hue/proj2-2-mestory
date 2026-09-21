// 백엔드가 준 긴 서술을 화면에서 읽을 수 있는 "줄 목록"으로 나눈다.
//
// 왜 프론트에서 나누나:
//   llm.py가 항목마다 줄바꿈을 넣도록 출력 계약을 조였지만(Field description),
//   그건 앞으로 만들어질 리포트에만 적용된다. 이미 저장된 리포트는 400~600자가
//   줄바꿈 0개로 한 덩어리다. 그래서 줄바꿈이 있으면 그걸 쓰고, 없으면 여기서 나눈다.
//
// 원칙: 이미 줄바꿈이 있으면 그것을 우선한다. 모델이 나눠 준 것이 언제나 더 정확하다.

/** " 2) " 앞에서 자른다. 앞의 공백이 조건이라 "(2026-09-12)"의 "12)"는 걸리지 않는다. */
const NUMBERED_STEP = /\s+(?=\d+\)\s)/;

/** "…진행. (추가권고) …" 처럼 문장이 끝난 뒤 오는 괄호 라벨 앞에서 자른다.
 *  마침표가 앞에 있어야 하므로 "1) (정비팀)"의 괄호는 걸리지 않는다. */
const LABEL_AFTER_SENTENCE = /(?<=[.!?])\s+(?=\([가-힣]{2,8}\))/;

/** 문장 끝(.!?) + 공백에서 자른다.
 *  뒤가 숫자나 닫는 괄호면 문장 끝이 아니라고 보고 넘어간다 — "1) …" 같은 항목 번호를
 *  문장으로 잘못 쪼개지 않기 위해서다. "17.9 min"은 마침표 뒤에 공백이 없어 애초에 안 걸린다. */
const SENTENCE_END = /(?<=[.!?])\s+(?![0-9)])/;

/** 빈 조각을 버리고, 너무 짧아 혼자 설 수 없는 조각은 앞줄에 도로 붙인다. */
function tidy(parts: string[]): string[] {
  const lines: string[] = [];
  for (const part of parts) {
    const line = part.trim();
    if (!line) continue;
    if (line.length <= 2 && lines.length > 0) {
      lines[lines.length - 1] += ` ${line}`;
      continue;
    }
    lines.push(line);
  }
  return lines;
}

/** 권장 조치처럼 "1) 2) 3)"으로 번호가 매겨진 글을 항목별로 나눈다. */
export function splitSteps(text?: string | null): string[] {
  if (!text) return [];
  if (text.includes("\n")) return tidy(text.split("\n"));
  const byNumber = text.split(NUMBERED_STEP);
  return tidy(byNumber.flatMap((part) => part.split(LABEL_AFTER_SENTENCE)));
}

/** 분석 참고 사항처럼 번호 없이 이어진 글을 문장별로 나눈다. */
export function splitSentences(text?: string | null): string[] {
  if (!text) return [];
  if (text.includes("\n")) return tidy(text.split("\n"));
  return tidy(text.split(SENTENCE_END));
}

/** 줄 목록의 각 줄이 "1)"처럼 번호로 시작하는지. 번호가 있으면 화면에서 번호를 따로 그리지 않는다. */
export function startsWithNumber(line: string): boolean {
  return /^\d+\)/.test(line);
}
