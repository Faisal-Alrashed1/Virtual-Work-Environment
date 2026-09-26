import { api, type ChatMessageApiOut, type TeamMessageApiOut } from "./api";

export interface ChatMessage {
  id: string;
  agentType: string;
  sender: "user" | "agent";
  content: string;
  createdAt: string;
}

/** A Team Room turn — agentType is null for the graduate's own messages,
 * since (unlike a 1:1 thread) the room isn't with one fixed agent. */
export interface TeamMessage {
  id: string;
  agentType: string | null;
  sender: "user" | "agent";
  content: string;
  createdAt: string;
}

function toChatMessage(m: ChatMessageApiOut): ChatMessage {
  return {
    id: m.id,
    agentType: m.agent_type,
    sender: m.sender_type,
    content: m.content,
    createdAt: m.created_at,
  };
}

function toTeamMessage(m: TeamMessageApiOut): TeamMessage {
  return {
    id: m.id,
    agentType: m.agent_type,
    sender: m.sender_type,
    content: m.content,
    createdAt: m.created_at,
  };
}

export async function fetchConversation(agent: string): Promise<ChatMessage[]> {
  const raw = await api.meeting.history(agent);
  return raw.map(toChatMessage);
}

/** Sends a message and returns the agent's reply. The user's own message
 * is persisted server-side before the reply is generated, so callers append
 * their message optimistically and only append the returned reply. */
export async function sendChatMessage(
  agent: string,
  content: string
): Promise<ChatMessage> {
  return toChatMessage(await api.meeting.send(agent, content));
}

/** The Team Room's shared thread — the graduate and their whole team in
 * one conversation. Each message is routed to whichever single teammate
 * fits best; see docs/TEAM_ROOM.md. */
export async function fetchTeamConversation(): Promise<TeamMessage[]> {
  const raw = await api.meeting.team.history();
  return raw.map(toTeamMessage);
}

export async function sendTeamMessage(content: string): Promise<TeamMessage> {
  return toTeamMessage(await api.meeting.team.send(content));
}
