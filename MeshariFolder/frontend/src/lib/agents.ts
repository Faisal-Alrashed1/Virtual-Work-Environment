// Mirrors backend/app/models.py's AgentType enum values exactly
// ("manager" | "mentor" | "hr") so this can plug straight into the API
// later without a mapping layer.
export type AgentId = "manager" | "mentor" | "hr";

export interface AgentMeta {
  id: AgentId;
  name: string;
  role: string;
  description: string;
  colorVar: string;
}

export const AGENTS: Record<AgentId, AgentMeta> = {
  manager: {
    id: "manager",
    name: "Manager",
    role: "Assigns your work",
    description:
      "Calibrates your first task against your CV, then keeps assigning work based on how the task thread goes.",
    colorVar: "--agent-manager",
  },
  mentor: {
    id: "mentor",
    name: "Mentor",
    role: "Reviews what you submit",
    description:
      "Reads the GitHub link on a submitted task, leaves feedback, and writes a structured review.",
    colorVar: "--agent-mentor",
  },
  hr: {
    id: "hr",
    name: "HR",
    role: "Tracks how you grow",
    description:
      "Reads your review history and the employee file to keep a running summary of your strengths and growth areas.",
    colorVar: "--agent-hr",
  },
};

export const AGENT_ORDER: AgentId[] = ["manager", "mentor", "hr"];
