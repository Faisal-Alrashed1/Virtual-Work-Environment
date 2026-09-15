// Mirrors backend/app/models.py's AgentType enum values exactly
// ("manager" | "mentor" | "hr") so this can plug straight into the API
// later without a mapping layer.
export type AgentId = "manager" | "mentor" | "hr";

// name/role/description used to live here as static English strings —
// they're translated now, in lib/i18n/en.ts and ar.ts under `agents.*`.
// This file keeps only what's locale-independent: the id set, its
// display order, and which CSS variable each agent's identity color
// reads from. Use lib/i18n/locale.tsx's useAgents() hook to get the
// full, translated AgentMeta for the current language.
export interface AgentMeta {
  id: AgentId;
  name: string;
  role: string;
  description: string;
  colorVar: string;
}

export const AGENT_COLOR_VAR: Record<AgentId, string> = {
  manager: "--agent-manager",
  mentor: "--agent-mentor",
  hr: "--agent-hr",
};

export const AGENT_ORDER: AgentId[] = ["manager", "mentor", "hr"];
