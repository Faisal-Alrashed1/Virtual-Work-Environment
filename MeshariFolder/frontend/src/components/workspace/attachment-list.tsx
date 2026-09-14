"use client";

import { useEffect, useState } from "react";
import { Download, FileText } from "lucide-react";
import type { TaskAttachment } from "@/lib/tasks";
import { downloadAttachment, fetchAttachmentBlob } from "@/lib/attachments";

function ImageThumbnail({ taskId, attachment }: { taskId: string; attachment: TaskAttachment }) {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;
    fetchAttachmentBlob(taskId, attachment.id)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [taskId, attachment.id]);

  return (
    <a
      href={url ?? undefined}
      target="_blank"
      rel="noreferrer"
      title={attachment.filename}
      className="block h-24 w-24 overflow-hidden rounded border border-border bg-bg-surface-raised"
    >
      {url ? (
        // Blob URL, not a static/remote asset — next/image's loader
        // doesn't apply here.
        // eslint-disable-next-line @next/next/no-img-element
        <img src={url} alt={attachment.filename} className="h-full w-full object-cover" />
      ) : (
        <div className="flex h-full w-full items-center justify-center">
          <span className="font-mono text-[10px] text-text-muted">...</span>
        </div>
      )}
    </a>
  );
}

interface AttachmentListProps {
  taskId: string;
  attachments: TaskAttachment[];
}

/** Images render as inline thumbnails; anything else is a download button.
 * Both fetch the file as an authenticated blob first (a plain <img src>
 * or <a href> can't attach the Bearer token the download endpoint needs). */
export function AttachmentList({ taskId, attachments }: AttachmentListProps) {
  if (attachments.length === 0) return null;
  const images = attachments.filter((a) => a.contentType.startsWith("image/"));
  const files = attachments.filter((a) => !a.contentType.startsWith("image/"));

  return (
    <div className="mt-3 flex flex-col gap-3">
      {images.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {images.map((a) => (
            <ImageThumbnail key={a.id} taskId={taskId} attachment={a} />
          ))}
        </div>
      )}
      {files.length > 0 && (
        <div className="flex flex-col gap-1.5">
          {files.map((a) => (
            <button
              key={a.id}
              type="button"
              onClick={() => downloadAttachment(taskId, a.id, a.filename)}
              className="flex items-center gap-2 rounded border border-border px-3 py-2 text-left text-sm text-text-secondary transition-colors hover:border-border-strong hover:text-text-primary"
            >
              <FileText className="h-3.5 w-3.5 shrink-0" />
              <span className="truncate">{a.filename}</span>
              <Download className="ml-auto h-3.5 w-3.5 shrink-0 text-text-muted" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
