type Line = { key: string; color: string; values: number[] };

type Props = {
  labels: string[];
  lines: Line[];
  maxY: number;
};

const WIDTH = 720;
const HEIGHT = 260;
const PAD_LEFT = 30;
const PAD_RIGHT = 12;
const PAD_TOP = 12;
const PAD_BOTTOM = 34;

function toPoints(values: number[], maxY: number) {
  const innerW = WIDTH - PAD_LEFT - PAD_RIGHT;
  const innerH = HEIGHT - PAD_TOP - PAD_BOTTOM;
  const step = innerW / (values.length - 1);
  return values.map((v, i) => {
    const x = PAD_LEFT + step * i;
    const y = PAD_TOP + innerH * (1 - v / maxY);
    return [x, y] as const;
  });
}

export default function TrendChart({ labels, lines, maxY }: Props) {
  const innerH = HEIGHT - PAD_TOP - PAD_BOTTOM;
  const ySteps = 5;

  return (
    <svg className="trend-chart" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label="라인별 다운타임 추이 그래프">
      {Array.from({ length: ySteps + 1 }, (_, i) => {
        const y = PAD_TOP + (innerH / ySteps) * i;
        const label = maxY - (maxY / ySteps) * i;
        return (
          <g key={i}>
            <line x1={PAD_LEFT} y1={y} x2={WIDTH - PAD_RIGHT} y2={y} className="trend-gridline" />
            <text x={PAD_LEFT - 8} y={y + 4} className="trend-axis-label" textAnchor="end">
              {label === 0 ? "0h" : `${label}h`}
            </text>
          </g>
        );
      })}

      {lines.map((line) => {
        const points = toPoints(line.values, maxY);
        const path = points.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x},${y}`).join(" ");
        return (
          <g key={line.key}>
            <path d={path} fill="none" stroke={line.color} strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" />
            {points.map(([x, y], i) => (
              <circle key={i} cx={x} cy={y} r={3.5} fill={line.color} stroke="#fff" strokeWidth={1.5} />
            ))}
          </g>
        );
      })}

      {labels.map((label, i) => {
        const innerW = WIDTH - PAD_LEFT - PAD_RIGHT;
        const step = innerW / (labels.length - 1);
        const x = PAD_LEFT + step * i;
        const [day, paren] = label.split("\n");
        return (
          <g key={i}>
            <text x={x} y={HEIGHT - 18} className="trend-axis-label" textAnchor="middle">{day}</text>
            <text x={x} y={HEIGHT - 5} className="trend-axis-label trend-axis-label-sub" textAnchor="middle">{paren}</text>
          </g>
        );
      })}
    </svg>
  );
}
