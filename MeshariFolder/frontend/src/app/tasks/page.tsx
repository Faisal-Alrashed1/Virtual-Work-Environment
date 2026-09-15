import { redirect } from "next/navigation";

// The task board moved into the full Jira-style /workspace. Kept as a
// redirect so existing links (and the review page's "back" links) still
// land somewhere sensible instead of 404ing.
export default function TasksPage() {
  redirect("/workspace");
}
