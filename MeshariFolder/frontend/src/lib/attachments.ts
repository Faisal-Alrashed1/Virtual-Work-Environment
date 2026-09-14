import { api } from "./api";

/** Fetches an attachment's bytes as a blob (authenticated — a plain
 * <img src> or <a href> can't attach the Bearer token). Callers turn this
 * into an object URL with URL.createObjectURL and revoke it on cleanup. */
export async function fetchAttachmentBlob(taskId: string, attachmentId: string): Promise<Blob> {
  return api.tasks.attachmentBlob(taskId, attachmentId);
}

/** Triggers a normal browser download for a non-image attachment. */
export async function downloadAttachment(
  taskId: string,
  attachmentId: string,
  filename: string
): Promise<void> {
  const blob = await fetchAttachmentBlob(taskId, attachmentId);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
