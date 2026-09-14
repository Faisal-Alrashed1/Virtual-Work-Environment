"use client";

import { FormEvent, useState } from "react";
import { Copy, Mail, Send, UserPlus } from "lucide-react";
import { api } from "@/lib/api";

type Invitation = {
  id: string;
  code: string;
  invite_url: string;
  status: string;
};

type InviteCandidatesProps = {
  organizationId?: string;
};

export default function InviteCandidates({ organizationId }: InviteCandidatesProps) {
  const [email, setEmail] = useState("");
  const [createdInvite, setCreatedInvite] = useState<Invitation | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  async function handleSendInvite(e: FormEvent) {
    e.preventDefault();
    if (!organizationId) return;
    setBusy(true);
    setMsg("");
    try {
      const res = await api<Invitation>(`/api/organizations/${organizationId}/invitations`, {
        method: "POST",
        body: JSON.stringify({ candidate_email: email }),
      });
      setCreatedInvite(res);
      setMsg("تم إنشاء رابط الدعوة بنجاح!");
      setEmail("");
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "تعذر إنشاء الدعوة");
    } finally {
      setBusy(false);
    }
  }

  function copyInviteLink() {
    if (!createdInvite) return;
    const fullUrl = `${window.location.origin}${createdInvite.invite_url}`;
    navigator.clipboard.writeText(fullUrl);
    setMsg("تم نسخ رابط الدعوة إلى الحافظة!");
  }

  return (
    <div className="panel side" style={{ padding: 24 }}>
      <h3 style={{ fontSize: 20, margin: "0 0 8px", display: "flex", alignItems: "center", gap: 8 }}>
        <UserPlus size={20} color="var(--teal)" /> إرسال ودعوة المرشحين (Candidate Invitations)
      </h3>
      <p style={{ fontSize: 14, color: "var(--muted)", marginBottom: 20 }}>
        أنشئ رابط دعوة مخصص لمرشح جديد أو موظف ينضم حديثًا للشركة للانخراط في دورة التقييم الأسبوعية.
      </p>

      <form onSubmit={handleSendInvite} style={{ maxWidth: 500 }}>
        <label style={{ display: "block", marginBottom: 6, fontSize: 14 }}>بريد المرشح (اختياري)</label>
        <div style={{ display: "flex", gap: 10, marginBottom: 15 }}>
          <input
            type="email"
            placeholder="candidate@example.com"
            value={email}
            onChange={e => setEmail(e.target.value)}
            disabled={!organizationId}
            style={{ flex: 1, padding: 12, borderRadius: 10, border: "1px solid var(--line)", font: "inherit" }}
          />
          <button className="btn" disabled={!organizationId || busy}>
            {busy ? "جارٍ الإنشاء…" : "إنشاء رابط الدعوة"}
          </button>
        </div>
      </form>

      {msg && (
        <div style={{ padding: 12, background: "#f0f8f5", borderRadius: 10, border: "1px solid var(--mint)", marginBottom: 15, fontSize: 14, fontWeight: "bold" }}>
          {msg}
        </div>
      )}

      {createdInvite && (
        <div style={{ background: "#ffffff", padding: 18, borderRadius: 14, border: "1px solid var(--line)", marginTop: 15 }}>
          <strong>تفاصيل رابط الدعوة المنشأ:</strong>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 10 }}>
            <input
              type="text"
              readOnly
              value={`${typeof window !== "undefined" ? window.location.origin : ""}${createdInvite.invite_url}`}
              style={{ flex: 1, padding: 10, borderRadius: 8, border: "1px solid var(--line)", background: "#f8faf9", font: "inherit", direction: "ltr" }}
            />
            <button className="btn secondary" onClick={copyInviteLink} style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <Copy size={16} /> نسخ الرابط
            </button>
          </div>
          <span style={{ fontSize: 12, color: "var(--muted)", display: "block", marginTop: 8 }}>
            رمز الدعوة: <code style={{ color: "var(--teal)" }}>{createdInvite.code}</code> · حالة الدعوة: {createdInvite.status}
          </span>
        </div>
      )}
    </div>
  );
}
