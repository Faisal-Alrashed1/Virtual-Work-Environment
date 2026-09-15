"use client";

import { useState } from "react";
import Link from "next/link";
import { GitPullRequest, Calendar, CircleCheck, Clock, Paperclip, X } from "lucide-react";
import { STATUS_ORDER, type Task } from "@/lib/tasks";
import { timeUntil, timeAgo } from "@/lib/format";
import { AttachmentList } from "@/components/workspace/attachment-list";
import { useAgents, useLocale, useStatusLabels } from "@/lib/i18n/locale";

export interface SubmitPayload {
  githubLink?: string;
  submissionText?: string;
  files?: File[];
}

interface TaskWorkspaceProps {
  task: Task;
  busy: "review" | "reply" | null;
  onAdvance: (payload?: SubmitPayload) => void;
}

const MAX_FILES = 5;

export function TaskWorkspace({ task, busy, onAdvance }: TaskWorkspaceProps) {
  const { t } = useLocale();
  const agents = useAgents();
  const statusLabels = useStatusLabels();
  const [linkDraft, setLinkDraft] = useState("");
  const [textDraft, setTextDraft] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const agent = agents[task.createdByAgent];

  const canSubmit = linkDraft.trim() || textDraft.trim() || files.length > 0;

  function addFiles(picked: FileList | null) {
    if (!picked) return;
    setFiles((prev) => [...prev, ...Array.from(picked)].slice(0, MAX_FILES));
  }

  function handleSubmit() {
    onAdvance({
      githubLink: linkDraft.trim() || undefined,
      submissionText: textDraft.trim() || undefined,
      files: files.length > 0 ? files : undefined,
    });
    setLinkDraft("");
    setTextDraft("");
    setFiles([]);
  }

  return (
    <div className="thin-scrollbar h-full overflow-y-auto">
      <div className="mx-auto max-w-2xl px-8 py-8">
        {/* meta line */}
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <span className="flex items-center gap-1.5">
            <span
              className="h-2 w-2 rounded-full"
              style={{ backgroundColor: `var(${agent.colorVar})` }}
            />
            <span className="font-mono text-[11px] text-text-muted">
              {t("taskWorkspace.assignedBy", { name: agent.name })}
            </span>
          </span>
          {task.deadline && (
            <span
              className={`flex items-center gap-1 font-mono text-[11px] ${
                task.isLate ? "text-danger" : "text-text-muted"
              }`}
            >
              <Calendar className="h-3 w-3" />
              {task.status === "reviewed"
                ? task.isLate
                  ? t("taskWorkspace.completedLate")
                  : t("taskWorkspace.completedOnTime")
                : t("taskWorkspace.due", { time: timeUntil(task.deadline) })}
            </span>
          )}
          <span className="flex items-center gap-1 font-mono text-[11px] text-text-muted">
            <Clock className="h-3 w-3" />
            {timeAgo(task.createdAt)}
          </span>
        </div>

        <h1 className="mt-4 text-2xl font-medium leading-snug text-text-primary">
          {task.title}
        </h1>

        {/* status progress bar */}
        <div className="mt-6">
          <div className="flex items-center gap-1.5">
            {STATUS_ORDER.map((s) => {
              const active =
                STATUS_ORDER.indexOf(s) <= STATUS_ORDER.indexOf(task.status);
              return (
                <span
                  key={s}
                  className={`h-1.5 flex-1 rounded ${
                    active ? "bg-accent" : "bg-border"
                  }`}
                />
              );
            })}
          </div>
          <div className="mt-2 flex justify-between">
            {STATUS_ORDER.map((s) => (
              <span
                key={s}
                className={`font-mono text-[10px] ${
                  s === task.status ? "text-text-primary" : "text-text-muted"
                }`}
              >
                {statusLabels[s]}
              </span>
            ))}
          </div>
        </div>

        {/* description */}
        <div className="mt-8">
          <p className="font-mono text-[11px] text-text-muted">{t("taskWorkspace.descriptionLabel")}</p>
          <p className="mt-2 whitespace-pre-line text-sm leading-relaxed text-text-secondary">
            {task.description}
          </p>
        </div>

        {/* action zone, status-driven */}
        <div className="mt-8 rounded border border-border bg-bg-surface p-5">
          {task.status === "todo" && (
            <>
              <p className="text-sm text-text-secondary">
                {t("taskWorkspace.readyStart")}
              </p>
              <button
                type="button"
                onClick={() => onAdvance()}
                className="mt-3 rounded border border-accent bg-accent px-5 py-2.5 text-sm font-medium text-accent-text transition-colors hover:bg-accent-strong"
              >
                {t("taskWorkspace.startThisTask")}
              </button>
            </>
          )}
          {task.status === "in_progress" && (
            <div className="flex flex-col gap-3">
              <div>
                <label className="font-mono text-[11px] text-text-muted">
                  {t("taskWorkspace.githubLinkLabel")}
                </label>
                <input
                  value={linkDraft}
                  onChange={(e) => setLinkDraft(e.target.value)}
                  placeholder={t("taskWorkspace.githubPlaceholder")}
                  dir="ltr"
                  disabled={busy === "review"}
                  className="mt-1.5 w-full rounded border border-border bg-bg-surface-raised px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-border-strong focus:outline-none disabled:opacity-50"
                />
              </div>

              <div>
                <label className="font-mono text-[11px] text-text-muted">
                  {t("taskWorkspace.notesLabel")}
                </label>
                <textarea
                  value={textDraft}
                  onChange={(e) => setTextDraft(e.target.value)}
                  rows={3}
                  placeholder={t("taskWorkspace.notesPlaceholder")}
                  disabled={busy === "review"}
                  className="mt-1.5 w-full resize-none rounded border border-border bg-bg-surface-raised px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-border-strong focus:outline-none disabled:opacity-50"
                />
              </div>

              <div>
                <label className="font-mono text-[11px] text-text-muted">
                  {t("taskWorkspace.filesLabel", { n: MAX_FILES })}
                </label>
                <div className="mt-1.5 flex flex-wrap items-center gap-2">
                  {files.map((f, i) => (
                    <span
                      key={i}
                      className="flex items-center gap-1.5 rounded border border-border bg-bg-surface-raised px-2.5 py-1 text-xs text-text-secondary"
                    >
                      {f.name}
                      <button
                        type="button"
                        onClick={() => setFiles((prev) => prev.filter((_, j) => j !== i))}
                        className="text-text-muted hover:text-text-primary"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </span>
                  ))}
                  {files.length < MAX_FILES && (
                    <label className="flex cursor-pointer items-center gap-1.5 rounded border border-dashed border-border px-2.5 py-1 text-xs text-text-muted transition-colors hover:border-border-strong hover:text-text-secondary">
                      <Paperclip className="h-3 w-3" />
                      {t("common.add")}
                      <input
                        type="file"
                        multiple
                        className="hidden"
                        onChange={(e) => addFiles(e.target.files)}
                      />
                    </label>
                  )}
                </div>
              </div>

              <button
                type="button"
                disabled={!canSubmit || busy === "review"}
                onClick={handleSubmit}
                className="self-start rounded border border-accent bg-accent px-5 py-2 text-sm font-medium text-accent-text transition-colors hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-40"
              >
                {busy === "review" ? t("taskWorkspace.submitting") : t("taskWorkspace.submitForReview")}
              </button>
            </div>
          )}
          {task.status === "submitted" && (
            <div className="flex items-center gap-2 text-sm text-text-secondary">
              <GitPullRequest className="h-4 w-4" />
              <span>
                {busy === "review" ? t("taskWorkspace.mentorReviewingNow") : t("taskWorkspace.waitingOnMentor")}
              </span>
            </div>
          )}
          {task.status === "reviewed" && (
            <div className="flex flex-col items-start gap-3">
              <div className="flex items-center gap-2 text-sm text-text-primary">
                <CircleCheck className="h-4 w-4 text-accent-ink" />
                <span>{t("taskWorkspace.reviewedByMentor")}</span>
              </div>
              <Link
                href={`/tasks/${task.id}/review`}
                className="rounded border border-accent bg-accent px-5 py-2.5 text-sm font-medium text-accent-text transition-colors hover:bg-accent-strong"
              >
                {t("taskWorkspace.seeFullReview")}
              </Link>
            </div>
          )}
        </div>

        {(task.githubLink || task.submissionText || task.attachments.length > 0) && (
          <div className="mt-4 rounded border border-border bg-bg-surface p-4">
            <p className="font-mono text-[11px] text-text-muted">{t("taskWorkspace.yourSubmission")}</p>
            {task.githubLink && (
              <a
                href={task.githubLink}
                target="_blank"
                rel="noreferrer"
                dir="ltr"
                className="mt-2 flex items-center gap-1.5 text-sm text-text-secondary transition-colors hover:text-text-primary"
              >
                <GitPullRequest className="h-3.5 w-3.5 shrink-0" /> {task.githubLink}
              </a>
            )}
            {task.submissionText && (
              <p className="mt-2 whitespace-pre-line text-sm leading-relaxed text-text-secondary">
                {task.submissionText}
              </p>
            )}
            <AttachmentList taskId={task.id} attachments={task.attachments} />
          </div>
        )}
      </div>
    </div>
  );
}
