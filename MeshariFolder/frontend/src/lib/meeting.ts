import { api, type ChatMessageApiOut } from "./api";

export interface ChatMessage {
  id: string;
  agentType: string;
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
