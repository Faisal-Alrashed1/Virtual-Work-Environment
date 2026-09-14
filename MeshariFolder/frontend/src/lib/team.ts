import { api, type AgentCatalogApiOut } from "./api";

export type ExtraAgent = AgentCatalogApiOut;

/** The graduate's selected optional agents on top of the default three
 * (Manager/Mentor/HR) — powers the board's agents graph, the "your team"
 * cards, and the orientation screen. */
export async function fetchMyExtraAgents(): Promise<ExtraAgent[]> {
  return api.onboarding.myAgents();
}
