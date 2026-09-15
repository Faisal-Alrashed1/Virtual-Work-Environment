interface RubricBarProps {
  label: string;
  score: number;
  max?: number;
}

export function RubricBar({ label, score, max = 5 }: RubricBarProps) {
  const pct = Math.max(0, Math.min(100, Math.round((score / max) * 100)));

  return (
    <div>
      <div className="flex items-center justify-between">
        <span className="text-sm text-text-secondary">{label}</span>
        <span className="font-mono text-xs text-text-muted">
          {score}/{max}
        </span>
      </div>
      <div className="mt-1.5 h-1.5 rounded-full bg-border">
        <div
          className="h-1.5 rounded-full bg-agent-mentor"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
