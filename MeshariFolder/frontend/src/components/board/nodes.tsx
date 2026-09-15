"use client";

import { Handle, Position, type NodeProps } from "reactflow";
import { motion } from "framer-motion";
import type { AgentId } from "@/lib/agents";
import { useAgents, useLocale } from "@/lib/i18n/locale";

const handleStyle = {
  width: 6,
  height: 6,
  background: "var(--border-strong)",
  border: "none",
};

const entrance = (index: number) => ({
  initial: { opacity: 0, scale: 0.9 },
  animate: { opacity: 1, scale: 1 },
  transition: { delay: 0.15 + index * 0.1, duration: 0.35, ease: "easeOut" as const },
});

export interface UserNodeData {
  index: number;
}

export function UserNode({ data }: NodeProps<UserNodeData>) {
  const { t } = useLocale();
  return (
    <motion.div
      {...entrance(data.index)}
      className="w-[140px] rounded border border-border-strong bg-bg-surface-raised px-3 py-2 text-center"
    >
      <span className="font-medium text-text-primary">{t("common.you")}</span>
      <p className="mt-0.5 font-mono text-[11px] text-text-muted">{t("board.entryPoint")}</p>
      <Handle type="source" position={Position.Bottom} style={handleStyle} />
    </motion.div>
  );
}

export interface AgentNodeData {
  agentId: AgentId;
  index: number;
  onSelect: (agentId: AgentId) => void;
}

export function AgentNode({ data }: NodeProps<AgentNodeData>) {
  const agents = useAgents();
  const meta = agents[data.agentId];
  return (
    <motion.button
      type="button"
      onClick={() => data.onSelect(data.agentId)}
      {...entrance(data.index)}
      className="w-[200px] cursor-pointer rounded border border-border bg-bg-surface px-4 py-3 text-start transition-colors hover:border-border-strong"
    >
      <Handle type="target" position={Position.Top} style={handleStyle} />
      <div className="flex items-center gap-2">
        <span
          className="h-2 w-2 rounded-full"
          style={{ backgroundColor: `var(${meta.colorVar})` }}
        />
        <span className="font-medium text-text-primary">{meta.name}</span>
      </div>
      <p className="mt-1 text-xs text-text-secondary">{meta.role}</p>
      <span dir="ltr" className="mt-2 inline-block font-mono text-[11px] text-text-muted">
        agent_type: {meta.id}
      </span>
      <Handle type="source" position={Position.Bottom} style={handleStyle} />
    </motion.button>
  );
}

export interface CustomAgentNodeData {
  agentId: string;
  name: string;
  description: string;
  index: number;
  onSelect: (agentId: string) => void;
}

/** An extra agent the graduate added during onboarding, on top of the
 * default three — same shape as AgentNode, but reads its name/description
 * straight from props (there's no fixed lib/agents.ts entry for these,
 * and the catalog's own name/description come from the backend, not the
 * frontend dictionary — Stage 2's catalog is English-only for now, see
 * the i18n doc) and uses a neutral dot instead of one of the three
 * reserved agent colors, per DESIGN.md. */
export function CustomAgentNode({ data }: NodeProps<CustomAgentNodeData>) {
  return (
    <motion.button
      type="button"
      onClick={() => data.onSelect(data.agentId)}
      {...entrance(data.index)}
      className="w-[200px] cursor-pointer rounded border border-dashed border-border bg-bg-surface px-4 py-3 text-start transition-colors hover:border-border-strong"
    >
      <Handle type="target" position={Position.Top} style={handleStyle} />
      <div className="flex items-center gap-2">
        <span className="h-2 w-2 rounded-full bg-text-muted" />
        <span className="font-medium text-text-primary">{data.name}</span>
      </div>
      <p className="mt-1 text-xs text-text-secondary">{data.description}</p>
      <span dir="ltr" className="mt-2 inline-block font-mono text-[11px] text-text-muted">
        agent_type: {data.agentId}
      </span>
      <Handle type="source" position={Position.Bottom} style={handleStyle} />
    </motion.button>
  );
}

export interface EmployeeFileNodeData {
  index: number;
  onSelect: () => void;
}

export function EmployeeFileNode({ data }: NodeProps<EmployeeFileNodeData>) {
  const { t } = useLocale();
  return (
    <motion.button
      type="button"
      onClick={data.onSelect}
      {...entrance(data.index)}
      className="w-[240px] cursor-pointer rounded border-2 border-accent bg-bg-surface-raised px-4 py-3 text-start"
    >
      <Handle
        type="target"
        position={Position.Top}
        style={{ ...handleStyle, background: "var(--accent)" }}
      />
      <span className="font-medium text-text-primary">{t("detailPanel.employeeFileTitle")}</span>
      <p className="mt-1 text-xs text-text-secondary">{t("board.employeeFileNodeTagline")}</p>
      <span className="mt-2 inline-block font-mono text-[11px] text-text-muted">
        employee_file
      </span>
    </motion.button>
  );
}
