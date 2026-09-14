import { AGENTS, type AgentId } from "./agents";
import type { ExtraAgent } from "./team";

export interface AgentDisplay {
  name: string;
  role: string;
  colorVar: string | null;
}

/** Looks up display info for an agent id that might be one of the fixed
 * default three or one of the graduate's extra roster agents — the
 * catalog can grow, so this never assumes a closed set. Falls back to
 * the raw id if somehow neither matches (shouldn't happen in practice). */
export function agentDisplay(id: string, extraAgents: ExtraAgent[]): AgentDisplay {
  if (id in AGENTS) {
    const m = AGENTS[id as AgentId];
    return { name: m.name, role: m.role, colorVar: m.colorVar };
  }
  const extra = extraAgents.find((a) => a.id === id);
  return { name: extra?.name ?? id, role: extra?.description ?? "", colorVar: null };
}
