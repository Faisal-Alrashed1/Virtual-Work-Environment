"use client";

import { FormEvent, useState } from "react";
import { Briefcase, Building2, CheckCircle2, FileText, UserCheck, UserPlus, Users } from "lucide-react";
import { api } from "@/lib/api";

type Organization = { id: string; name: string };
type Campaign = { id: string; organization_id: string; title: string; job_role: string };
type Task = { id: string; title: string; brief: string; status: string };

export default function CompanyPage() {
  const [activeTab, setActiveTab] = useState<"setup" | "knowledge" | "campaigns" | "decisions">("setup");
  const [org, setOrg] = useState<Organization | null>(null);
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [lastTask, setLastTask] = useState<Task | null>(null);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  async function createOrg(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setMsg("");
    const f = new FormData(e.currentTarget);
    try {
      const r = await api<Organization>("/api/organizations", {
        method: "POST",
        body: JSON.stringify({ name: f.get("name") }),
      });
      setOrg(r);
      setMsg(`تم إنشاء مساحة الشركة بنجاح: ${r.name}`);
      setActiveTab("knowledge");
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "تعذر إنشاء الشركة");
    } finally {
      setBusy(false);
    }
  }

  async function uploadKnowledge(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!org) return;
    setBusy(true);
    setMsg("");
    const f = new FormData(e.currentTarget);
    try {
      await api(`/api/organizations/${org.id}/knowledge`, {
        method: "POST",
        body: JSON.stringify({
          name: f.get("name"),
          content: f.get("content"),
          attested_synthetic: f.get("attested") === "on",
        }),
      });
      setMsg("تمت فهرسة سياسة/معرفة الشركة بنجاح وربطها بقاعدة المعرفة (Vector DB).");
      setActiveTab("campaigns");
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "تعذر رفع المعرفة");
    } finally {
      setBusy(false);
    }
  }

  async function createCampaign(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!org) return;
    setBusy(true);
    setMsg("");
    const f = new FormData(e.currentTarget);
    try {
      const c = await api<Campaign>("/api/campaigns", {
        method: "POST",
        body: JSON.stringify({
          organization_id: org.id,
          title: f.get("title"),
          job_role: f.get("job_role"),
        }),
      });
      setCampaign(c);
      setMsg(`تمت إضافة حملة تقييم المرشحين: ${c.title}`);
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "تعذر إنشاء الحملة");
    } finally {
      setBusy(false);
    }
  }

  async function draftTask(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!campaign) return;
    setBusy(true);
    setMsg("");
    const f = new FormData(e.currentTarget);
    try {
      const t = await api<Task>(`/api/campaigns/${campaign.id}/tasks`, {
        method: "POST",
        body: JSON.stringify({
          candidate_user_id: f.get("candidate_id"),
          title: f.get("title"),
          brief: f.get("brief"),
          acceptance_criteria: [f.get("c1"), f.get("c2")].filter(Boolean),
          difficulty: Number(f.get("difficulty") || 1),
        }),
      });
      setLastTask(t);
      setMsg(`تمت مسودة مهمة المرشح بحالة PENDING_APPROVAL`);
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "تعذر مسودة المهمة");
    } finally {
      setBusy(false);
    }
  }

  async function approveTask() {
    if (!campaign || !lastTask) return;
    setBusy(true);
    setMsg("");
    try {
      await api(`/api/campaigns/${campaign.id}/tasks/${lastTask.id}/approve`, { method: "POST" });
      setLastTask({ ...lastTask, status: "TO_DO" });
      setMsg("تمت اعتماد المهمة بنجاح وظهرت في حساب المرشح!");
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "تعذر اعتماد المهمة");
    } finally {
      setBusy(false);
    }
  }

  async function recordDecision(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!campaign) return;
    setBusy(true);
    setMsg("");
    const f = new FormData(e.currentTarget);
    try {
      await api(`/api/campaigns/${campaign.id}/candidates/${f.get("candidate_id")}/decision`, {
        method: "POST",
        body: JSON.stringify({
          decision: f.get("decision"),
          notes: f.get("notes"),
        }),
      });
      setMsg("تم تسجيل قرار التوظيف بنجاح في سجل الشركة.");
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "تعذر تسجيل القرار");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div className="brand">
          <span className="brandmark">V</span> Venv للشركات (Recruiter Portal)
        </div>
        <nav className="nav">
          <a href="/dashboard">فضاء الطالب</a>
          <a className="active">لوحة التوظيف</a>
        </nav>
      </header>

      <div className="content" style={{ maxWidth: 1100 }}>
        <span className="eyebrow">مسار مسؤول التوظيف (B2B Track)</span>
        <h1 className="title">إدارة تقييم المرشحين وقواعد معرفة الشركات</h1>
        <p className="subtitle">
          أنشئ مساحة الشركة، ارفع الملفات لـ Vector DB، اعتمد مهام التقييم قبل ظهورها للمرشحين، وسجل قرارات التوظيف.
        </p>

        {/* Tab Selector */}
        <div style={{ display: "flex", gap: 10, marginTop: 20, flexWrap: "wrap" }}>
          <button className={`btn ${activeTab === "setup" ? "" : "secondary"}`} onClick={() => setActiveTab("setup")}>
            <Building2 size={16} style={{ marginLeft: 6 }} /> 1. إعداد المساحة
          </button>
          <button className={`btn ${activeTab === "knowledge" ? "" : "secondary"}`} onClick={() => setActiveTab("knowledge")}>
            <FileText size={16} style={{ marginLeft: 6 }} /> 2. قاعدة المعرفة (RAG)
          </button>
          <button className={`btn ${activeTab === "campaigns" ? "" : "secondary"}`} onClick={() => setActiveTab("campaigns")}>
            <Briefcase size={16} style={{ marginLeft: 6 }} /> 3. الحملات والمهام
          </button>
          <button className={`btn ${activeTab === "decisions" ? "" : "secondary"}`} onClick={() => setActiveTab("decisions")}>
            <UserCheck size={16} style={{ marginLeft: 6 }} /> 4. قرارات التوظيف
          </button>
        </div>

        {msg && (
          <div className="panel side" style={{ marginTop: 20, background: "#f0f8f5", border: "1px solid var(--mint)" }}>
            <span style={{ fontWeight: "bold" }}>{msg}</span>
          </div>
        )}

        {/* Tab 1: Setup */}
        {activeTab === "setup" && (
          <div className="panel side form" style={{ marginTop: 20 }}>
            <h2>إنشاء مساحة الشركة المنفصلة</h2>
            <form onSubmit={createOrg}>
              <label>اسم الشركة أو المنظمة</label>
              <input name="name" required placeholder="مثال: شركة التقنية المتطورة" />
              <button className="btn" disabled={busy}>
                {busy ? "جارٍ الإنشاء…" : "إنشاء مساحة الشركة"}
              </button>
            </form>
          </div>
        )}

        {/* Tab 2: Knowledge Base */}
        {activeTab === "knowledge" && (
          <div className="panel side form" style={{ marginTop: 20 }}>
            <h2>رفع محتوى قاعدة المعرفة (Synthetic Handbook)</h2>
            <p style={{ fontSize: 14, color: "var(--muted)" }}>
              يُشترط تأكيد أن البيانات وهمية أو منزوعة الهوية. سيتم تحويل النص إلى Embeddings في Vector DB الخاص بالشركة.
            </p>
            <form onSubmit={uploadKnowledge}>
              <label>اسم المصدر / الدليل</label>
              <input name="name" required placeholder="مثال: دليل مهام المطورين المستجدين" disabled={!org} />

              <label>محتوى الدليل والمعايير (نص خام)</label>
              <textarea
                name="content"
                rows={6}
                required
                disabled={!org}
                placeholder="الصق نص السياسات أو المعايير أو أسلوب العمل هنا..."
              />

              <label style={{ display: "flex", alignItems: "center", cursor: "pointer", margin: "10px 0" }}>
                <input name="attested" type="checkbox" style={{ width: "auto", marginLeft: 8 }} required disabled={!org} />
                <span>أؤكد أن البيانات وهمية أو منزوعة الهوية بالكامل</span>
              </label>

              <button className="btn" disabled={!org || busy}>
                {busy ? "جارٍ الفهرسة…" : "فهرسة وربط مع قاعدة المعرفة"}
              </button>
            </form>
          </div>
        )}

        {/* Tab 3: Campaigns & Tasks */}
        {activeTab === "campaigns" && (
          <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", gap: 20, marginTop: 20 }}>
            <div className="panel side form">
              <h2>إنشاء حملة تقييم</h2>
              <form onSubmit={createCampaign}>
                <label>عنوان الحملة</label>
                <input name="title" required placeholder="مثال: حملة مطوري Backend 2026" disabled={!org} />

                <label>المسمى الوظيفي المستهدف</label>
                <input name="job_role" required placeholder="مثال: Backend Engineer" disabled={!org} />

                <button className="btn" disabled={!org || busy}>
                  إنشاء الحملة
                </button>
              </form>
            </div>

            <div className="panel side form">
              <h2>مسودة مهمة وتقييم للمرشح</h2>
              <form onSubmit={draftTask}>
                <label>معرّف المرشح (User ID)</label>
                <input name="candidate_id" required placeholder="معرف المرشح المسجل" disabled={!campaign} />

                <label>عنوان المهمة</label>
                <input name="title" required placeholder="عنوان المهمة المخصصة" disabled={!campaign} />

                <label>الوصف الموجز</label>
                <textarea name="brief" rows={3} required placeholder="وصف تفصيلي للشرط المطلوبة" disabled={!campaign} />

                <label>معايير النجاح (Criterion 1 & 2)</label>
                <input name="c1" required placeholder="المعيار الأول" disabled={!campaign} />
                <input name="c2" placeholder="المعيار الثاني (اختياري)" disabled={!campaign} />

                <button className="btn" disabled={!campaign || busy}>
                  حفظ المسودة (PENDING_APPROVAL)
                </button>
              </form>

              {lastTask && lastTask.status === "PENDING_APPROVAL" && (
                <div style={{ marginTop: 15, padding: 12, background: "#fff8ec", borderRadius: 12, border: "1px solid var(--amber)" }}>
                  <p style={{ margin: 0, fontSize: 13 }}>المهمة الآن في حالة بانتظار اعتماد مسؤول التوظيف.</p>
                  <button className="btn" onClick={approveTask} style={{ marginTop: 8, width: "100%" }} disabled={busy}>
                    اعتماد المهمة وإرسالها للمرشح
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Tab 4: Decisions */}
        {activeTab === "decisions" && (
          <div className="panel side form" style={{ marginTop: 20 }}>
            <h2>تسجيل قرار التوظيف النهائي (Hiring Decision)</h2>
            <p style={{ fontSize: 14, color: "var(--muted)" }}>
              النظام لا يتخذ قرار التوظيف آليًا؛ مسؤول التوظيف البشري هو من يسجل القرار بعد الاطلاع على تقارير الوكلاء.
            </p>
            <form onSubmit={recordDecision}>
              <label>معرف المرشح (Candidate User ID)</label>
              <input name="candidate_id" required placeholder="معرف المرشح" disabled={!campaign} />

              <label>القرار النهائي</label>
              <select name="decision" required disabled={!campaign}>
                <option value="advance">قبول وانتقال للمرحلة التالية (Advance)</option>
                <option value="hold">تعليق / قائمة الانتظار (Hold)</option>
                <option value="reject">عدم قبول (Reject)</option>
              </select>

              <label>ملاحظات القرار</label>
              <textarea name="notes" rows={3} placeholder="مبررات القرار والتوصيات..." disabled={!campaign} />

              <button className="btn" disabled={!campaign || busy}>
                حفظ قرار التوظيف
              </button>
            </form>
          </div>
        )}
      </div>
    </main>
  );
}
