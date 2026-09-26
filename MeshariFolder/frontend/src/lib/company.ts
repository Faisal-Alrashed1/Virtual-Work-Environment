import {
  api,
  type CompanyProjectApiOut,
  type CompanyRegisterPayload,
  type CompanyStudentApiOut,
  type CompanyStudentDetailApiOut,
  type InvitationApiOut,
  type JobTitleApiOut,
  type KnowledgeMaterialApiOut,
  type OrganizationApiOut,
  type RAGQueryResultApiOut,
} from "./api";

export interface Organization {
  id: string;
  name: string;
  field: string | null;
  joinCode: string;
}

export interface JobTitle {
  id: string;
  title: string;
  description: string | null;
  createdAt: string;
  materialCount: number;
  chunkCount: number;
}

export interface KnowledgeMaterial {
  id: string;
  jobTitleId: string;
  filename: string | null;
  chunkCount: number;
  createdAt: string;
  preview: string;
}

export interface RAGChunk {
  id: string;
  materialId: string;
  content: string;
  score: number;
}

export interface CompanyProjectSummary {
  id: string;
  jobTitleId: string;
  title: string;
  description: string;
  hasMaterials: boolean;
  createdAt: string;
}

export interface Invitation {
  id: string;
  jobTitleId: string;
  jobTitle: string;
  companyProjectId: string | null;
  companyProjectTitle: string | null;
  invitedEmail: string;
  status: "pending" | "accepted" | "declined";
  emailSent: boolean;
  createdAt: string;
  respondedAt: string | null;
}

export interface CompanyStudent {
  invitationId: string;
  studentName: string;
  studentEmail: string;
  jobTitle: string;
  companyProjectTitle: string | null;
  projectTitle: string | null;
  projectStatus: "active" | "completed" | null;
  currentWeekNumber: number | null;
  taskCounts: Record<string, number>;
}

export interface CompanyTask {
  id: string;
  title: string;
  description: string;
  status: string;
  githubLink: string | null;
  submissionText: string | null;
  deadline: string | null;
  submittedAt: string | null;
  completedAt: string | null;
}

export interface CompanyReview {
  id: string;
  agentType: string;
  kind: string;
  content: string;
  metrics: Record<string, unknown> | null;
  createdAt: string;
}

export interface CompanyStudentWeek {
  weekNumber: number;
  status: "active" | "completed";
  startedAt: string;
  targetEndAt: string;
  endedAt: string | null;
  tasks: CompanyTask[];
  reviews: CompanyReview[];
}

export interface CompanyStudentDetail extends CompanyStudent {
  weeks: CompanyStudentWeek[];
}

function toOrganization(o: OrganizationApiOut): Organization {
  return { id: o.id, name: o.name, field: o.field, joinCode: o.join_code };
}

function toJobTitle(j: JobTitleApiOut): JobTitle {
  return {
    id: j.id,
    title: j.title,
    description: j.description,
    createdAt: j.created_at,
    materialCount: j.material_count,
    chunkCount: j.chunk_count,
  };
}

function toMaterial(m: KnowledgeMaterialApiOut): KnowledgeMaterial {
  return {
    id: m.id,
    jobTitleId: m.job_title_id,
    filename: m.filename,
    chunkCount: m.chunk_count,
    createdAt: m.created_at,
    preview: m.preview,
  };
}

function toCompanyProject(p: CompanyProjectApiOut): CompanyProjectSummary {
  return {
    id: p.id,
    jobTitleId: p.job_title_id,
    title: p.title,
    description: p.description,
    hasMaterials: p.has_materials,
    createdAt: p.created_at,
  };
}

function toInvitation(i: InvitationApiOut): Invitation {
  return {
    id: i.id,
    jobTitleId: i.job_title_id,
    jobTitle: i.job_title,
    companyProjectId: i.company_project_id,
    companyProjectTitle: i.company_project_title,
    invitedEmail: i.invited_email,
    status: i.status,
    emailSent: i.email_sent,
    createdAt: i.created_at,
    respondedAt: i.responded_at,
  };
}

/** Founds a new company, or joins an existing one via its join code —
 * see app/schemas.py's CompanyRegister for which fields matter for which
 * shape. Doesn't log the rep in; call login() after, same as the
 * student register flow. */
export async function registerCompany(payload: CompanyRegisterPayload) {
  const raw = await api.company.register(payload);
  return { user: raw.user, organization: toOrganization(raw.organization) };
}

export async function fetchMyCompany(): Promise<Organization> {
  return toOrganization(await api.company.me());
}

export async function fetchJobTitles(): Promise<JobTitle[]> {
  const raw = await api.company.listJobTitles();
  return raw.map(toJobTitle);
}

export async function fetchJobTitle(id: string): Promise<JobTitle> {
  return toJobTitle(await api.company.getJobTitle(id));
}

export async function createJobTitle(title: string, description?: string): Promise<JobTitle> {
  return toJobTitle(await api.company.createJobTitle(title, description));
}

export async function fetchMaterials(jobTitleId: string): Promise<KnowledgeMaterial[]> {
  const raw = await api.company.listMaterials(jobTitleId);
  return raw.map(toMaterial);
}

export async function uploadMaterial(
  jobTitleId: string,
  text?: string,
  file?: File
): Promise<KnowledgeMaterial> {
  return toMaterial(await api.company.uploadMaterial(jobTitleId, text, file));
}

export async function queryKnowledgeBase(
  jobTitleId: string,
  query: string,
  k?: number
): Promise<{ query: string; chunks: RAGChunk[] }> {
  const raw: RAGQueryResultApiOut = await api.company.query(jobTitleId, query, k);
  return {
    query: raw.query,
    chunks: raw.chunks.map((c) => ({
      id: c.id,
      materialId: c.material_id,
      content: c.content,
      score: c.score,
    })),
  };
}

export async function createCompanyProject(
  jobTitleId: string,
  title: string,
  description: string,
  materialsText?: string,
  files?: File[]
): Promise<CompanyProjectSummary> {
  return toCompanyProject(
    await api.company.createProject(jobTitleId, title, description, materialsText, files)
  );
}

export async function fetchCompanyProjects(jobTitleId: string): Promise<CompanyProjectSummary[]> {
  const raw = await api.company.listProjects(jobTitleId);
  return raw.map(toCompanyProject);
}

export async function createInvitation(
  jobTitleId: string,
  invitedEmail: string,
  companyProjectId?: string
): Promise<Invitation> {
  return toInvitation(await api.company.createInvitation(jobTitleId, invitedEmail, companyProjectId));
}

export async function fetchCompanyInvitations(): Promise<Invitation[]> {
  const raw = await api.company.listInvitations();
  return raw.map(toInvitation);
}

function toStudent(s: CompanyStudentApiOut): CompanyStudent {
  return {
    invitationId: s.invitation_id,
    studentName: s.student_name,
    studentEmail: s.student_email,
    jobTitle: s.job_title,
    companyProjectTitle: s.company_project_title,
    projectTitle: s.project_title,
    projectStatus: s.project_status,
    currentWeekNumber: s.current_week_number,
    taskCounts: s.task_counts,
  };
}

export function toStudentDetail(s: CompanyStudentDetailApiOut): CompanyStudentDetail {
  return {
    ...toStudent(s),
    weeks: s.weeks.map((w) => ({
      weekNumber: w.week_number,
      status: w.status,
      startedAt: w.started_at,
      targetEndAt: w.target_end_at,
      endedAt: w.ended_at,
      tasks: w.tasks.map((t) => ({
        id: t.id,
        title: t.title,
        description: t.description,
        status: t.status,
        githubLink: t.github_link,
        submissionText: t.submission_text,
        deadline: t.deadline,
        submittedAt: t.submitted_at,
        completedAt: t.completed_at,
      })),
      reviews: w.reviews.map((r) => ({
        id: r.id,
        agentType: r.agent_type,
        kind: r.kind,
        content: r.content,
        metrics: r.metrics_json,
        createdAt: r.created_at,
      })),
    })),
  };
}

export async function fetchCompanyStudents(): Promise<CompanyStudent[]> {
  const raw = await api.company.listStudents();
  return raw.map(toStudent);
}

export async function fetchCompanyStudentDetail(invitationId: string): Promise<CompanyStudentDetail> {
  return toStudentDetail(await api.company.getStudent(invitationId));
}
