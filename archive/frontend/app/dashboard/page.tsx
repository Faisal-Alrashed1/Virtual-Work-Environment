"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Bell, Briefcase, CheckCircle2, Code2, Compass, Layers, LineChart, MessageSquare, Send, Sparkles, Star, UserRound, UsersRound } from "lucide-react";
import AgentChat from "@/components/AgentChat";
import { api } from "@/lib/api";

type Task = {
  id: string;
  title: string;
  brief: string;
  status: string;
  criteria: string[];
  difficulty: number;
};

type Decision = {
  type: "decision";
  outcome: "excellent" | "improve";
  improvements?: string[];
};

type Evaluation = {
  agent: string;
  scores: Record<string, number>;
  rationale: string;
  confidence: number;
  evidence: ({ type: string } | Decision)[];
};

type WeeklyReport = {
  completed_tasks: number;
  senior_report: { summary: string; technical_average?: number };
  manager_evaluation: { technical_score: number; summary: string };
  hr_evaluation: { behavior_score: number; summary: string };
  next_difficulty: number;
  previous_performance_score: number;
  performance_score: number;
};

type Work = {
  career_path?: {
    focus?: string;
    assessment?: { score: number; starting_difficulty: number; gaps?: string[] };
    stages?: { name: string; status: string; skills: string[] }[];
  };
  project_status: "ready" | "kickoff" | "active" | "week_complete";
  project_overview?: string;
  completed_this_week: number;
  tasks: Task[];
  notifications: { id: string; body: string }[];
  evaluations: Evaluation[];
  weekly_report?: WeeklyReport;
  performance_score: number;
};

const phases = ["TO_DO", "IN_PROGRESS", "UNDER_REVIEW", "DISCUSSION", "REVIEWED"];
const phaseNames: Record<string, string> = {
  TO_DO: "جاهزة",
  IN_PROGRESS: "قيد التنفيذ",
  UNDER_REVIEW: "مراجعة Senior",
  DISCUSSION: "مناقشة وتحسين",
  REVIEWED: "مكتملة",
};

export default function Dashboard() {
  const [data, setData] = useState<Work | null>(null);
  const [activeView, setActiveView] = useState<"senior" | "manager" | "hr">("senior");
  const [chatAgent, setChatAgent] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [submitMode, setSubmitMode] = useState<"code" | "github">("code");
  const [error, setError] = useState("");

  const load = useCallback(() => {
    return api<Work>("/api/workspace")
      .then(res => {
        setData(res);
      })
      .catch(reason => setError(reason instanceof Error ? reason.message : "تعذر تحميل مساحة العمل"));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const activeTask = data?.tasks.find(item => item.status !== "REVIEWED");

  async function projectAction(path: "join" | "start" | "next-week") {
    setBusy(true);
    setError("");
    try {
      await api(`/api/project/${path}`, { method: "POST" });
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "تعذر إجراء العملية");
    } finally {
      setBusy(false);
    }
  }

  async function startTask() {
    if (!activeTask) return;
    setBusy(true);
    setError("");
    try {
      await api(`/api/tasks/${activeTask.id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status: "IN_PROGRESS" }),
      });
      await load();
      setActiveView("senior");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "تعذر بدء المهمة");
    } finally {
      setBusy(false);
    }
  }

  async function submitTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeTask) return;
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    const submission =
      submitMode === "code"
        ? { code: form.get("code"), language: form.get("language") }
        : { github_url: form.get("github_url") };
    try {
      await api(`/api/tasks/${activeTask.id}/submit`, {
        method: "POST",
        body: JSON.stringify({
          ...submission,
          summary: form.get("summary"),
          challenges: form.get("challenges"),
        }),
      });
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "تعذر تسليم المهمة");
    } finally {
      setBusy(false);
    }
  }

  async function closeTask() {
    if (!activeTask) return;
    setBusy(true);
    setError("");
    try {
      await api(`/api/tasks/${activeTask.id}/complete-discussion`, { method: "POST" });
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "ناقش مراجعة Senior أولًا قبل الإغلاق");
    } finally {
      setBusy(false);
    }
  }

  const phaseIndex = Math.max(0, phases.indexOf(activeTask?.status || "TO_DO"));
  const seniorReview = data?.evaluations.find(item => item.agent === "senior");
  const decision = seniorReview?.evidence.find(item => item.type === "decision") as Decision | undefined;

  return (
    <main className="shell">
      <header className="topbar">
        <div className="brand">
          <span className="brandmark">V</span> Venv Platform
        </div>
        <nav className="nav">
          <a className="active">فضاء العمل</a>
          <a href="/company">مسار الشركات</a>
        </nav>
        <Bell size={20} />
      </header>

      <div className="content">
        <span className="eyebrow">Junior Web Workspace</span>
        <h1 className="title">دورة عمل مهيكلة مع فريقك الذكي</h1>
        <p className="subtitle">
          تفاعل مع Senior للمهام والتسليم، واطلع على خطة Manager للمشروع، وتابع تقييم HR ونصائح الأداء المهني.
        </p>

        {error && <div className="panel side error flow-message" style={{ marginTop: 15 }}>{error}</div>}

        {/* Project Initial States */}
        {data?.project_status === "ready" && (
          <section className="panel kickoff-card" style={{ padding: 30, marginTop: 20 }}>
            <span className="eyebrow">الخطوة الأولى</span>
            <h2>انضم إلى مشروع Web Developer</h2>
            <p>بعد الانضمام سيشرح Manager المشروع كاملًا بنيته والمطلوب منك قبل البدء بالمهام اليومية.</p>
            <button className="btn" onClick={() => projectAction("join")} disabled={busy}>
              {busy ? "جارٍ الانضمام…" : "انضم إلى المشروع"}
            </button>
          </section>
        )}

        {data?.project_status === "kickoff" && (
          <section className="panel kickoff-card" style={{ padding: 30, marginTop: 20 }}>
            <span className="eyebrow">اجتماع تعريف المشروع · Manager</span>
            <h2>المشروع ومتطلبات التدريب</h2>
            <p className="project-overview" style={{ whiteSpace: "pre-line", lineHeight: 1.7, background: "#f8faf9", padding: 18, borderRadius: 14 }}>
              {data.project_overview}
            </p>
            <button className="btn" onClick={() => projectAction("start")} disabled={busy}>
              {busy ? "جارٍ تجهيز أول مهمة…" : "فهمت المشروع — ابدأ أول مهمة مع Senior"}
            </button>
          </section>
        )}

        {/* Active Project Workspace */}
        {(data?.project_status === "active" || data?.project_status === "week_complete") && (
          <>
            {data.notifications[0] && (
              <div className="workspace-alert" style={{ marginTop: 15 }}>
                <Bell size={16} />
                <span>{data.notifications[0].body}</span>
              </div>
            )}

            {/* Team Interactive Circle */}
            <div className="grid" style={{ marginTop: 20 }}>
              <section className="panel workspace circle-workspace">
                <strong className="space-title">دائرة الفريق · التفاعل والتنفيذ</strong>
                
                {/* Manager Node */}
                <button
                  className={`node manager ${activeView === "manager" ? "active-agent" : ""}`}
                  onClick={() => setActiveView("manager")}
                >
                  <span className="avatar">
                    <Briefcase />
                  </span>
                  <strong>Manager</strong>
                  <small>هدف المشروع والرؤية</small>
                </button>

                {/* Senior Node */}
                <button
                  className={`node senior ${activeView === "senior" ? "active-agent" : ""}`}
                  onClick={() => setActiveView("senior")}
                >
                  <span className="avatar">
                    <Compass />
                  </span>
                  <strong>Senior</strong>
                  <small>المهمة اليومية والمراجعة</small>
                </button>

                {/* User Node */}
                <div className="node user">
                  <span className="avatar">
                    <UserRound />
                  </span>
                  <strong>أنت · Junior</strong>
                  <small>تنفّذ وتسلم الكود</small>
                </div>

                {/* HR Node */}
                <button
                  className={`node hr ${activeView === "hr" ? "active-agent" : ""}`}
                  onClick={() => setActiveView("hr")}
                >
                  <span className="avatar">
                    <UsersRound />
                  </span>
                  <strong>HR</strong>
                  <small>التقييم والتقدم والنصائح</small>
                </button>
              </section>

              {/* Navigation View Selector */}
              <aside className="panel side" style={{ display: "flex", flexDirection: "column", gap: 15 }}>
                <div>
                  <strong className="eyebrow">طريقة التصفح</strong>
                  <h3 style={{ margin: "5px 0 10px" }}>اختر واجهة العرض</h3>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  <button
                    className={`btn ${activeView === "senior" ? "" : "secondary"}`}
                    onClick={() => setActiveView("senior")}
                    style={{ textAlign: "right", display: "flex", alignItems: "center", gap: 10 }}
                  >
                    <Compass size={18} />
                    <span>واجهة Senior (المهمة والتسليم)</span>
                  </button>
                  <button
                    className={`btn ${activeView === "manager" ? "" : "secondary"}`}
                    onClick={() => setActiveView("manager")}
                    style={{ textAlign: "right", display: "flex", alignItems: "center", gap: 10 }}
                  >
                    <Briefcase size={18} />
                    <span>واجهة Manager (هدف المشروع)</span>
                  </button>
                  <button
                    className={`btn ${activeView === "hr" ? "" : "secondary"}`}
                    onClick={() => setActiveView("hr")}
                    style={{ textAlign: "right", display: "flex", alignItems: "center", gap: 10 }}
                  >
                    <UsersRound size={18} />
                    <span>واجهة HR (التقييم والنصائح)</span>
                  </button>
                </div>

                <div style={{ marginTop: "auto", paddingTop: 15, borderTop: "1px solid var(--line)" }}>
                  <div className="week-progress">
                    <strong>تقدم الأسبوع الحالي</strong>
                    <span>{data.completed_this_week}/5 مهام</span>
                  </div>
                  <div className="diagnostic-progress" style={{ marginTop: 8 }}>
                    <span style={{ width: `${data.completed_this_week * 20}%` }} />
                  </div>
                </div>
              </aside>
            </div>

            {/* ISOLATED VIEW CONTENT */}
            <div style={{ marginTop: 24 }}>

              {/* 1. SENIOR ISOLATED VIEW (Structured Task & Review) */}
              {activeView === "senior" && (
                <section className="panel side" style={{ padding: 28 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20, flexWrap: "wrap", gap: 10 }}>
                    <div>
                      <span className="eyebrow" style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <Compass size={16} /> المشرف التقني المباشر · Senior Developer
                      </span>
                      <h2 style={{ fontSize: 24, margin: "4px 0" }}>المهمة اليومية ومراجعة التسليم</h2>
                    </div>
                    <button className="btn secondary" onClick={() => setChatAgent("senior")} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <MessageSquare size={16} /> محادثة مباشرة مع Senior
                    </button>
                  </div>

                  {activeTask ? (
                    <div className="task" style={{ padding: 22 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                        <span className="status">{phaseNames[activeTask.status] || activeTask.status}</span>
                        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                          <span style={{ fontSize: 13, color: "var(--muted)" }}>درجة الصعوبة:</span>
                          {Array.from({ length: 5 }).map((_, i) => (
                            <Star key={i} size={14} fill={i < activeTask.difficulty ? "var(--amber)" : "none"} color="var(--amber)" />
                          ))}
                        </div>
                      </div>

                      <h3 style={{ fontSize: 20, margin: "10px 0 8px" }}>{activeTask.title}</h3>
                      <p style={{ fontSize: 15, lineHeight: 1.6, color: "var(--ink)" }}>{activeTask.brief}</p>

                      {/* Task Stepper */}
                      <div className="lifecycle" style={{ margin: "20px 0" }}>
                        {phases.map((phase, index) => (
                          <span key={phase} className={`life-step ${index <= phaseIndex ? "active" : ""}`}>
                            {phaseNames[phase]}
                          </span>
                        ))}
                      </div>

                      {/* Criteria Checklist */}
                      <div style={{ background: "#f8faf9", padding: 16, borderRadius: 14, margin: "16px 0" }}>
                        <strong style={{ display: "block", marginBottom: 10 }}>معايير النجاح المطلوبة:</strong>
                        <ul className="criteria" style={{ listStyle: "none", padding: 0 }}>
                          {activeTask.criteria.map((item, idx) => (
                            <li key={idx} style={{ display: "flex", alignItems: "center", gap: 8, margin: "8px 0" }}>
                              <CheckCircle2 size={16} color="var(--teal)" />
                              <span>{item}</span>
                            </li>
                          ))}
                        </ul>
                      </div>

                      {/* Task Start / Submission Form */}
                      {activeTask.status === "TO_DO" && (
                        <div style={{ marginTop: 20 }}>
                          <button className="btn" onClick={startTask} disabled={busy}>
                            {busy ? "جارٍ التفعيل…" : "ابدأ تنفيذ المهمة"}
                          </button>
                        </div>
                      )}

                      {(activeTask.status === "IN_PROGRESS" || activeTask.status === "DISCUSSION") && (
                        <form className="submission-box" onSubmit={submitTask} style={{ marginTop: 20 }}>
                          <strong>{activeTask.status === "DISCUSSION" ? "إرسال محاولة محسنة إلى Senior" : "تسليم المحاولة إلى Senior"}</strong>
                          <div className="submission-tabs" style={{ marginTop: 10 }}>
                            <button
                              type="button"
                              className={`btn ${submitMode === "code" ? "" : "secondary"}`}
                              onClick={() => setSubmitMode("code")}
                            >
                              كود محلي (Inline Code)
                            </button>
                            <button
                              type="button"
                              className={`btn ${submitMode === "github" ? "" : "secondary"}`}
                              onClick={() => setSubmitMode("github")}
                            >
                              رابط GitHub
                            </button>
                          </div>

                          {submitMode === "code" ? (
                            <>
                              <select name="language" defaultValue="python" style={{ width: "100%", padding: 10, margin: "10px 0 6px" }}>
                                <option value="python">Python</option>
                                <option value="javascript">JavaScript</option>
                                <option value="typescript">TypeScript</option>
                                <option value="html">HTML / CSS</option>
                              </select>
                              <textarea
                                className="code-editor"
                                name="code"
                                required
                                rows={10}
                                dir="ltr"
                                placeholder="# اكتب أو الصق حل الكود هنا"
                              />
                            </>
                          ) : (
                            <input
                              name="github_url"
                              type="url"
                              required
                              placeholder="https://github.com/username/repository"
                              style={{ width: "100%", padding: 12, margin: "10px 0" }}
                            />
                          )}

                          <textarea
                            name="summary"
                            minLength={10}
                            required
                            rows={3}
                            placeholder="ملخص التنفيذ: اشرح ما قمت ببنائه وكيف تحققت من معايير المهمة"
                          />
                          <textarea
                            name="challenges"
                            rows={2}
                            placeholder="التحديات (اختياري): ما النقاط التي واجهت فيها صعوبة؟"
                          />
                          <button className="btn" disabled={busy} style={{ marginTop: 10 }}>
                            {busy ? "جارٍ تحليل المحاولة…" : "أرسل المحاولة إلى Senior"}
                          </button>
                        </form>
                      )}

                      {/* Structured Senior Review Results */}
                      {activeTask.status === "DISCUSSION" && seniorReview && (
                        <div className={`review-result ${decision?.outcome}`} style={{ marginTop: 24, padding: 20, borderRadius: 16, border: "1px solid var(--line)" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                            <span className="review-badge" style={{ fontSize: 13, fontWeight: "bold" }}>
                              {decision?.outcome === "excellent" ? "عمل رائع ومستوفٍ للمعايير" : "توصية بالمناقشة والتحسين"}
                            </span>
                            <span style={{ fontSize: 13, color: "var(--muted)" }}>درجة الثقة: {seniorReview.confidence}/5</span>
                          </div>

                          <h3 style={{ margin: "12px 0 6px" }}>تحليل Senior الفني</h3>
                          <p style={{ lineHeight: 1.6 }}>{seniorReview.rationale}</p>

                          <div className="review-scores" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 10, margin: "15px 0" }}>
                            {Object.entries(seniorReview.scores).map(([name, score]) => (
                              <div key={name} style={{ background: "#f5f7f5", padding: 10, borderRadius: 10, textAlign: "center" }}>
                                <span style={{ fontSize: 12, display: "block", color: "var(--muted)" }}>{name}</span>
                                <strong style={{ fontSize: 16 }}>{score}/5</strong>
                              </div>
                            ))}
                          </div>

                          {Boolean(decision?.improvements?.length) && (
                            <div style={{ margin: "15px 0" }}>
                              <strong>الخطوات العملية للتحسين:</strong>
                              <ul style={{ paddingRight: 20, marginTop: 6 }}>
                                {decision!.improvements!.map((item, idx) => (
                                  <li key={idx} style={{ margin: "4px 0" }}>{item}</li>
                                ))}
                              </ul>
                            </div>
                          )}

                          <div className="task-actions" style={{ marginTop: 15, display: "flex", gap: 10 }}>
                            <button className="btn" onClick={closeTask} disabled={busy}>
                              {decision?.outcome === "excellent" ? "انتقل للمهمة التالية" : "اعتمد المراجعة وأنهِ المهمة"}
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div style={{ textAlign: "center", padding: 40 }}>
                      <p>اكتملت جميع مهام هذا الأسبوع أو يتم تجهيز المهمة التالية.</p>
                      {data?.project_status === "week_complete" && (
                        <button className="btn" onClick={() => projectAction("next-week")} disabled={busy}>
                          ابدأ الأسبوع التالي بالمستوى الجديد
                        </button>
                      )}
                    </div>
                  )}
                </section>
              )}

              {/* 2. MANAGER ISOLATED VIEW (Main Goal & Project Overview) */}
              {activeView === "manager" && (
                <section className="panel side" style={{ padding: 28 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20, flexWrap: "wrap", gap: 10 }}>
                    <div>
                      <span className="eyebrow" style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <Briefcase size={16} /> المدير الهندسي · Engineering Manager
                      </span>
                      <h2 style={{ fontSize: 24, margin: "4px 0" }}>الهدف الأساسي ورؤية المشروع</h2>
                    </div>
                    <button className="btn secondary" onClick={() => setChatAgent("manager")} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <MessageSquare size={16} /> محادثة مباشرة مع Manager
                    </button>
                  </div>

                  <div className="grid" style={{ gridTemplateColumns: "1.2fr 1fr", gap: 20, marginTop: 10 }}>
                    <div style={{ background: "#f8faf9", padding: 20, borderRadius: 18, border: "1px solid var(--line)" }}>
                      <h3 style={{ display: "flex", alignItems: "center", gap: 8, margin: "0 0 12px" }}>
                        <Sparkles size={18} color="var(--teal)" /> هدف التدريب المحوري (Main Goal)
                      </h3>
                      <p style={{ fontSize: 16, fontWeight: 500, lineHeight: 1.6, color: "var(--ink)" }}>
                        {data?.career_path?.focus || "تطوير تطبيق Web متكامل محلي من الواجهة حتى قاعدة البيانات مع تطبيق أفضل الممارسات."}
                      </p>

                      <div style={{ marginTop: 20, paddingTop: 15, borderTop: "1px solid var(--line)" }}>
                        <strong>الدور المستهدف:</strong> Junior Web Developer<br />
                        <strong>المشروع النشط:</strong> Junior Web Workspace<br />
                        <strong>مستوى الصعوبة الحالي:</strong> {data?.career_path?.assessment?.starting_difficulty || 1} / 5
                      </div>
                    </div>

                    <div style={{ background: "white", padding: 20, borderRadius: 18, border: "1px solid var(--line)" }}>
                      <h3 style={{ display: "flex", alignItems: "center", gap: 8, margin: "0 0 12px" }}>
                        <Layers size={18} color="var(--teal)" /> مراحل خريطة التعلم
                      </h3>
                      <div className="path" style={{ flexDirection: "column" }}>
                        {(data?.career_path?.stages || [
                          { name: "أساسيات Web", status: "current", skills: ["HTML", "CSS", "JavaScript", "Git"] },
                          { name: "تطبيق متكامل", status: "next", skills: ["Frontend", "Backend", "API", "Database"] },
                          { name: "جودة المشروع", status: "future", skills: ["Testing", "Security", "Deployment"] },
                        ]).map((stage, idx) => (
                          <div key={idx} className={`stage ${stage.status === "current" ? "current" : ""}`} style={{ padding: 12, borderRadius: 10, background: stage.status === "current" ? "#eef8f5" : "#f9fbf9" }}>
                            <strong>المرحلة {idx + 1}: {stage.name}</strong>
                            <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 4 }}>
                              المهارات: {stage.skills.join(" · ")}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>

                  <div style={{ marginTop: 24, padding: 20, background: "#ffffff", borderRadius: 18, border: "1px solid var(--line)" }}>
                    <h3 style={{ margin: "0 0 10px" }}>نظرة عامة على هيكل المشروع والمخرجات</h3>
                    <p style={{ lineHeight: 1.7, color: "var(--muted)" }}>
                      {data?.project_overview || "يتكون المشروع من خمس مهام أسبوعية متتابعة تحت إشراف Senior. بعد انتهاء الخمس مهام يرفع Senior تقريره الفني إلى Manager لتقييم الأداء التقني، متبوعًا بتقييم HR السلوكي لتحديث مستواك التراكمي."}
                    </p>
                  </div>
                </section>
              )}

              {/* 3. HR ISOLATED VIEW (Evaluation, Progress & Tips) */}
              {activeView === "hr" && (
                <section className="panel side" style={{ padding: 28 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20, flexWrap: "wrap", gap: 10 }}>
                    <div>
                      <span className="eyebrow" style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <UsersRound size={16} /> الموارد البشرية · HR & Performance
                      </span>
                      <h2 style={{ fontSize: 24, margin: "4px 0" }}>لوحة تقييم الأداء والسلوك والتقدم</h2>
                    </div>
                    <button className="btn secondary" onClick={() => setChatAgent("hr")} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <MessageSquare size={16} /> محادثة مباشرة مع HR
                    </button>
                  </div>

                  <div className="grid" style={{ gridTemplateColumns: "1fr 1.5fr", gap: 20, marginTop: 10 }}>
                    {/* Score Card */}
                    <div style={{ background: "var(--ink)", color: "white", padding: 24, borderRadius: 20, textAlign: "center", display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center" }}>
                      <span style={{ fontSize: 13, color: "#a8c5bf" }}>درجة الأداء التراكمية</span>
                      <div style={{ fontSize: 56, fontWeight: 700, margin: "10px 0" }}>
                        {data?.performance_score ?? 50}
                        <span style={{ fontSize: 20, color: "#87a8a2" }}> / 100</span>
                      </div>
                      <p style={{ fontSize: 13, color: "#bfd6d1", maxWidth: 220 }}>
                        تتحدث تلقائيًا بعد كل أسبوع (70% تقني + 30% سلوكي).
                      </p>
                    </div>

                    {/* Behavioral & Communication Metrics */}
                    <div style={{ background: "white", padding: 20, borderRadius: 18, border: "1px solid var(--line)" }}>
                      <h3 style={{ margin: "0 0 14px", display: "flex", alignItems: "center", gap: 8 }}>
                        <LineChart size={18} color="var(--teal)" /> مؤشرات الانضباط والتواصل
                      </h3>
                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                        <div style={{ background: "#f8faf9", padding: 14, borderRadius: 12 }}>
                          <span style={{ fontSize: 12, color: "var(--muted)" }}>الاستمرارية والتسليم:</span>
                          <strong style={{ display: "block", fontSize: 15, marginTop: 4, color: "var(--teal)" }}>منضبط (Punctual)</strong>
                        </div>
                        <div style={{ background: "#f8faf9", padding: 14, borderRadius: 12 }}>
                          <span style={{ fontSize: 12, color: "var(--muted)" }}>التواصل مع Senior:</span>
                          <strong style={{ display: "block", fontSize: 15, marginTop: 4, color: "var(--teal)" }}>متواصل بانتظام</strong>
                        </div>
                        <div style={{ background: "#f8faf9", padding: 14, borderRadius: 12 }}>
                          <span style={{ fontSize: 12, color: "var(--muted)" }}>الاستجابة للملاحظات:</span>
                          <strong style={{ display: "block", fontSize: 15, marginTop: 4, color: "var(--teal)" }}>ممتازة (Responsive)</strong>
                        </div>
                        <div style={{ background: "#f8faf9", padding: 14, borderRadius: 12 }}>
                          <span style={{ fontSize: 12, color: "var(--muted)" }}>المهام اليومية المسلمة:</span>
                          <strong style={{ display: "block", fontSize: 15, marginTop: 4 }}>{data?.completed_this_week}/5 مهام</strong>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Tailored Advice & Tips */}
                  <div style={{ marginTop: 24, background: "#f4f9f7", padding: 22, borderRadius: 18, border: "1px solid #d4e8e3" }}>
                    <h3 style={{ margin: "0 0 12px", display: "flex", alignItems: "center", gap: 8, color: "var(--teal)" }}>
                      <Sparkles size={18} /> نصائح HR لتطوير أدائك المهني
                    </h3>
                    <ul style={{ paddingRight: 20, margin: 0, lineHeight: 1.8 }}>
                      <li><strong>التخطيط قبل الكود:</strong> اشرح خطتك بأسلوب قصير لـ Senior قبل البدء بكتابة الكود للحصول على أفضل التلميحات.</li>
                      <li><strong>جودة التسليم:</strong> تأكد من اختبار الكود محليًا والتحقق من عدم وجود أسرار أو مفاتيح داخل الملفات.</li>
                      <li><strong>إغلاق المهام:</strong> عند إرجاع محاولة تحتاج تحسينًا، ناقش النقاط مع Senior ثم أرسل التحديث واعتمد التقييم.</li>
                    </ul>
                  </div>

                  {/* Weekly Report History */}
                  {data?.weekly_report && (
                    <div style={{ marginTop: 24, padding: 22, background: "white", borderRadius: 18, border: "1px solid var(--line)" }}>
                      <h3>ملخص آخر تقرير أسبوعي معتمد</h3>
                      <div className="evaluation-grid" style={{ marginTop: 12 }}>
                        <article className="evaluation-card">
                          <h4>تقرير Senior الفني</h4>
                          <p>{data.weekly_report.senior_report.summary}</p>
                          <strong>{data.weekly_report.completed_tasks}/5 مهام</strong>
                        </article>
                        <article className="evaluation-card">
                          <h4>تقييم Manager التقني</h4>
                          <p>{data.weekly_report.manager_evaluation.summary}</p>
                          <strong>{data.weekly_report.manager_evaluation.technical_score}/5</strong>
                        </article>
                        <article className="evaluation-card">
                          <h4>تقييم HR السلوكي</h4>
                          <p>{data.weekly_report.hr_evaluation.summary}</p>
                          <strong>{data.weekly_report.hr_evaluation.behavior_score}/5</strong>
                        </article>
                      </div>
                    </div>
                  )}
                </section>
              )}
            </div>
          </>
        )}
      </div>

      {/* Direct Chat Modal - Opened ONLY when explicitly clicked */}
      {chatAgent && (
        <AgentChat
          agent={chatAgent}
          onClose={() => {
            setChatAgent(null);
            load();
          }}
          taskId={activeTask?.id}
        />
      )}
    </main>
  );
}
