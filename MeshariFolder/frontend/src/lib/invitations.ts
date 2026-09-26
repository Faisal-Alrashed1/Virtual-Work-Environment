import { api, type InvitationDetailApiOut } from "./api";
import { toStudentDetail, type CompanyStudentDetail } from "./company";

/** A student's own view of an invitation — everything needed to give
 * informed consent before accepting (dataSharedNotice), or to decline.
 * See lib/company.ts's Invitation for the company's own view of one it
 * sent — same underlying row, different shape for a different audience. */
export interface InvitationDetail {
  id: string;
  organizationName: string;
  jobTitle: string;
  companyProjectTitle: string | null;
  status: "pending" | "accepted" | "declined";
  createdAt: string;
  respondedAt: string | null;
  dataSharedNotice: string;
}

function toDetail(i: InvitationDetailApiOut): InvitationDetail {
  return {
    id: i.id,
    organizationName: i.organization_name,
    jobTitle: i.job_title,
    companyProjectTitle: i.company_project_title,
    status: i.status,
    createdAt: i.created_at,
    respondedAt: i.responded_at,
    dataSharedNotice: i.data_shared_notice,
  };
}

export async function fetchMyInvitations(): Promise<InvitationDetail[]> {
  const raw = await api.invitations.mine();
  return raw.map(toDetail);
}

/** consent must be explicitly true — the backend refuses (400) a missing
 * or false consent rather than assuming it from the act of calling this
 * at all. See app/schemas.py's INVITATION_DATA_NOTICE. */
export async function acceptInvitation(id: string, consent: boolean): Promise<InvitationDetail> {
  return toDetail(await api.invitations.accept(id, consent));
}

export async function declineInvitation(id: string): Promise<InvitationDetail> {
  return toDetail(await api.invitations.decline(id));
}

/** Exactly what the company that sent this invitation can currently see
 * about you — the literal same data their own roster detail view shows
 * them (reuses company.ts's toStudentDetail/CompanyStudentDetail
 * rather than a separate type), not a description of the promise but
 * the promise checked live. 404s until the invitation is accepted. */
export async function fetchMyVisibility(invitationId: string): Promise<CompanyStudentDetail> {
  return toStudentDetail(await api.invitations.visibility(invitationId));
}
