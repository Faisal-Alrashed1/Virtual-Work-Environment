"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { AGENTS } from "@/lib/agents";
import { useRequireAuth } from "@/lib/auth-context";
import { ApiError } from "@/lib/api";
import { fetchTaskDetail, type Task } from "@/lib/tasks";
import { fetchTaskReview, type Review } from "@/lib/reviews";
import { RubricBar } from "@/components/rubric-bar";
import { AttachmentList } from "@/components/workspace/attachment-list";

interface ReviewPageProps {
  params: Promise<{ id: string }>;
}

export default function ReviewPage({ params }: ReviewPageProps) {
  const { id } = use(params);
  const { user, loading: authLoading } = useRequireAuth();

  const [task, setTask] = useState<Task | null>(null);
  const [review, setReview] = useState<Review | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    Promise.all([fetchTaskDetail(id), fetchTaskReview(id)])
      .then(([t, r]) => {
        setTask(t);
        setReview(r);
      })
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Couldn't load this review.")
      )
      .finally(() => setLoading(false));
  }, [id, user]);

  const mentor = AGENTS.mentor;

  if (authLoading || !user) {
    return (
      <main className="flex flex-1 items-center justify-center">
        <p className="text-sm text-text-muted">Loading...</p>
      </main>
    );
  }

  return (
    <main className="min-h-dvh">
      <header className="flex items-center justify-between border-b border-border px-6 py-4">
        <div>
          <Link
            href="/workspace"
            className="font-mono text-xs text-text-muted hover:text-text-secondary"
          >
            venv / workspace
          </Link>
          <h1 className="mt-1 text-lg font-medium text-text-primary">
            Mentor&apos;s review
          </h1>
        </div>
      </header>

      <div className="mx-auto max-w-2xl px-6 py-8">
        {loading ? (
          <p className="text-sm text-text-muted">Loading...</p>
        ) : error ? (
          <p className="text-sm text-danger">{error}</p>
        ) : !task ? (
          <p className="text-sm text-text-secondary">Task not found.</p>
        ) : (
          <>
            <div className="rounded border border-border bg-bg-surface p-4">
              <p className="font-mono text-[11px] text-text-muted">task</p>
              <p className="mt-1 text-sm font-medium text-text-primary">
                {task.title}
              </p>
              {task.githubLink && (
                <p className="mt-2 font-mono text-[11px] text-text-muted">
                  {task.githubLink}
                </p>
              )}
              {task.submissionText && (
                <p className="mt-2 whitespace-pre-line text-sm leading-relaxed text-text-secondary">
                  {task.submissionText}
                </p>
              )}
              <AttachmentList taskId={task.id} attachments={task.attachments} />
            </div>

            {!review ? (
              <p className="mt-8 text-sm text-text-secondary">
                No review yet for this task.
              </p>
            ) : (
              <>
                <div className="mt-6 flex items-center gap-2">
                  <span
                    className="h-2.5 w-2.5 rounded-full"
                    style={{ backgroundColor: `var(${mentor.colorVar})` }}
                  />
                  <span className="text-sm font-medium text-text-primary">
                    {review.verdict === "approved" ? "Approved" : "Needs changes"}
                  </span>
                  <span className="font-mono text-[11px] text-text-muted">
                    by {mentor.name}
                  </span>
                </div>

                <p className="mt-4 text-sm leading-relaxed text-text-secondary">
                  {review.content}
                </p>

                <div className="mt-8 flex flex-col gap-4 rounded border border-border bg-bg-surface p-4">
                  {review.categories.map((category) => (
                    <RubricBar
                      key={category.key}
                      label={category.label}
                      score={category.score}
                    />
                  ))}
                </div>

                <div className="mt-8">
                  <p className="font-mono text-[11px] text-text-muted">comments</p>
                  <div className="mt-3 flex flex-col gap-3">
                    {review.comments.map((comment) => {
                      const categoryLabel =
                        review.categories.find((c) => c.key === comment.category)
                          ?.label ?? comment.category;
                      return (
                        <div
                          key={comment.id}
                          className="rounded border border-border bg-bg-surface p-3"
                        >
                          <span className="font-mono text-[11px] text-text-muted">
                            {categoryLabel}
                          </span>
                          <p className="mt-1 text-sm text-text-secondary">
                            {comment.content}
                          </p>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </>
            )}
          </>
        )}

        <Link
          href="/workspace"
          className="mt-10 inline-block text-xs text-text-muted hover:text-text-secondary"
        >
          Back to task board
        </Link>
      </div>
    </main>
  );
}
