"use client";

import { useMemo } from "react";
import ReactFlow, {
  Background,
  BackgroundVariant,
  Controls,
  type Edge,
  type Node,
} from "reactflow";
import "reactflow/dist/style.css";
import { AGENT_ORDER } from "@/lib/agents";
import type { ExtraAgent } from "@/lib/team";
import { AgentNode, CustomAgentNode, EmployeeFileNode, UserNode } from "@/components/board/nodes";
import type { BoardSelection } from "@/components/board/detail-panel";

const nodeTypes = {
  agent: AgentNode,
  customAgent: CustomAgentNode,
  user: UserNode,
  employeeFile: EmployeeFileNode,
};

const GAP = 260;
const START_X = 40;
const ROW_Y = 200;

interface FlowSectionProps {
  onSelect: (selection: BoardSelection) => void;
  /** Optional agents the graduate added during onboarding, on top of the
   * default three — rendered as extra nodes in the same row so the team
   * graph actually reflects who's really on the team. */
  extraAgents: ExtraAgent[];
}

/**
 * The agents graph — now the board's whole right column. Interactive
 * again: the graph pans and zooms (Meshari asked for that back), with
 * Controls for zoom/fit and nodes still clickable to open the detail
 * drawer. Fills its parent, so the parent must be a sized/relative box.
 *
 * Stage 2: the row now scales with however many optional agents the
 * graduate picked during onboarding (0 to however many the catalog
 * grows to) — the default three plus extras are laid out left to right
 * at a fixed gap, and the user/employee-file nodes stay centered above
 * and below whatever that total width ends up being.
 */
export function FlowSection({ onSelect, extraAgents }: FlowSectionProps) {
  const totalAgents = AGENT_ORDER.length + extraAgents.length;
  const centerX = START_X + ((totalAgents - 1) * GAP) / 2;

  const nodes: Node[] = useMemo(
    () => [
      { id: "user", type: "user", position: { x: centerX - 70, y: 20 }, data: { index: 0 } },
      ...AGENT_ORDER.map((agentId, i) => ({
        id: agentId,
        type: "agent",
        position: { x: START_X + i * GAP, y: ROW_Y },
        data: { agentId, index: i + 1, onSelect },
      })),
      ...extraAgents.map((agent, i) => ({
        id: agent.id,
        type: "customAgent",
        position: { x: START_X + (AGENT_ORDER.length + i) * GAP, y: ROW_Y },
        data: {
          agentId: agent.id,
          name: agent.name,
          description: agent.description,
          index: AGENT_ORDER.length + i + 1,
          onSelect,
        },
      })),
      {
        id: "employee-file",
        type: "employeeFile",
        position: { x: centerX - 120, y: 400 },
        data: { index: totalAgents + 1, onSelect: () => onSelect("employee-file") },
      },
    ],
    [onSelect, extraAgents, centerX, totalAgents]
  );

  const edges: Edge[] = useMemo(() => {
    const allAgentIds = [...AGENT_ORDER, ...extraAgents.map((a) => a.id)];
    return [
      ...allAgentIds.map((agentId) => ({
        id: `user-${agentId}`,
        source: "user",
        target: agentId,
        style: { stroke: "var(--border-strong)", strokeWidth: 1 },
      })),
      ...allAgentIds.map((agentId) => ({
        id: `${agentId}-file`,
        source: agentId,
        target: "employee-file",
        animated: true,
        style: { stroke: "var(--accent)", strokeWidth: 1, strokeDasharray: "4 3" },
      })),
    ];
  }, [extraAgents]);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      fitView
      fitViewOptions={{ padding: 0.3 }}
      proOptions={{ hideAttribution: true }}
      nodesConnectable={false}
      nodesDraggable={false}
      minZoom={0.4}
      maxZoom={1.5}
      className="bg-bg-base"
    >
      <Background variant={BackgroundVariant.Lines} gap={32} color="var(--line-grid)" />
      <Controls
        showInteractive={false}
        className="!border-border !bg-bg-surface [&_button]:!border-border [&_button]:!bg-bg-surface [&_button:hover]:!bg-bg-surface-raised [&_button_svg]:!fill-text-secondary"
      />
    </ReactFlow>
  );
}
