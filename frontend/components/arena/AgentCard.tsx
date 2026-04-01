"use client";

const AGENT_COLORS = [
  "#007BFF",
  "#00E676",
  "#FF6B6B",
  "#FFD93D",
  "#6C5CE7",
  "#A29BFE",
  "#FD79A8",
  "#00CEC9",
];

export interface AgentCardProps {
  name: string;
  role: string;
  goals: string[];
  modelId: string;
  index: number;
}

export function AgentCard({ name, role, goals, modelId, index }: AgentCardProps) {
  const color = AGENT_COLORS[index % AGENT_COLORS.length];

  return (
    <div
      className="rounded-xl border bg-white p-5 shadow-sm"
      style={{ borderLeftColor: color, borderLeftWidth: 4 }}
    >
      <h3 className="text-lg font-semibold text-gray-900">{name}</h3>
      <span
        className="mt-1 inline-block rounded-full px-3 py-0.5 text-xs font-medium text-white"
        style={{ backgroundColor: color }}
      >
        {role}
      </span>
      <ul className="mt-3 space-y-1">
        {goals.map((goal, i) => (
          <li key={i} className="text-sm text-gray-600">
            • {goal}
          </li>
        ))}
      </ul>
      <p className="mt-3 text-xs text-gray-400">Model: {modelId}</p>
    </div>
  );
}
