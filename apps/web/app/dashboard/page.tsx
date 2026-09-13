"use client";

import {FormEvent, useCallback, useEffect, useState} from "react";
import {Bell, Briefcase, Compass, UserRound, UsersRound} from "lucide-react";
import AgentChat from "@/components/AgentChat";
import {api} from "@/lib/api";

type Task = {id: string; title: string; brief: string; status: string; criteria: string[]; difficulty: number};
type Decision = {type: "decision"; outcome: "excellent" | "improve"; improvements?: string[]};
type Evaluation = {agent: string; scores: Record<string, number>; rationale: string; confidence: number; evidence: ({type: string} | Decision)[]};
type WeeklyReport = {completed_tasks: number; senior_report: {summary: string; technical_average?: number}; manager_evaluation: {technical_score: number; summary: string}; hr_evaluation: {behavior_score: number; summary: string}; next_difficulty: number; previous_performance_score: number; performance_score: number};
type Work = {
  career_path?: {focus?: string; assessment?: {score: number; starting_difficulty: number}; stages?: {name: string; status: string; skills: string[]}[]};
  project_status: "ready" | "kickoff" | "active" | "week_complete"; project_overview?: string; completed_this_week: number;
  tasks: Task[]; notifications: {id: string; body: string}[]; evaluations: Evaluation[]; weekly_report?: WeeklyReport; performance_score: number;
};

const phases = ["TO_DO", "IN_PROGRESS", "UNDER_REVIEW", "DISCUSSION", "REVIEWED"];
const phaseNames: Record<string, string> = {TO_DO: "جاهزة", IN_PROGRESS: "قيد التنفيذ", UNDER_REVIEW: "مراجعة Senior", DISCUSSION: "مناقشة وتحسين", REVIEWED: "مكتملة"};

export default function Dashboard() {
  const [data, setData] = useState<Work | null>(null);
  const [agent, setAgent] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [submitMode, setSubmitMode] = useState<"code" | "github">("code");
  const [error, setError] = useState("");
  const load = useCallback(() => api<Work>("/api/workspace").then(setData).catch(reason => setError(reason instanceof Error ? reason.message : "تعذر تحميل مساحة العمل")), []);
  useEffect(() => { load(); }, [load]);
  const task = data?.tasks.find(item => item.status !== "REVIEWED");

  async function projectAction(path: "join" | "start" | "next-week") {
    setBusy(true); setError("");
    try { await api(`/api/project/${path}`, {method: "POST"}); await load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "تعذر بدء المشروع"); }
    finally { setBusy(false); }
  }

  async function startTask() {
    if (!task) return; setBusy(true); setError("");
    try { await api(`/api/tasks/${task.id}/status`, {method: "PATCH", body: JSON.stringify({status: "IN_PROGRESS"})}); await load(); setAgent("senior"); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "تعذر بدء المهمة"); }
    finally { setBusy(false); }
  }

  async function submitTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!task) return; setBusy(true); setError("");
    const form = new FormData(event.currentTarget);
    const submission = submitMode === "code" ? {code: form.get("code"), language: form.get("language")} : {github_url: form.get("github_url")};
    try { await api(`/api/tasks/${task.id}/submit`, {method: "POST", body: JSON.stringify({...submission, summary: form.get("summary"), challenges: form.get("challenges")})}); await load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "تعذر تسليم المهمة"); }
    finally { setBusy(false); }
  }

  async function closeTask() {
    if (!task) return; setBusy(true); setError("");
    try { await api(`/api/tasks/${task.id}/complete-discussion`, {method: "POST"}); await load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "ناقش مراجعة Senior أولًا"); }
    finally { setBusy(false); }
  }

  const phaseIndex = Math.max(0, phases.indexOf(task?.status || "TO_DO"));
  const seniorReview = data?.evaluations.find(item => item.agent === "senior");
  const decision = seniorReview?.evidence.find(item => item.type === "decision") as Decision | undefined;
  return <main className="shell">
    <header className="topbar"><div className="brand"><span className="brandmark">V</span> Venv</div><nav className="nav"><a className="active">فضاء العمل</a><a href="#career">مساري</a><a href="#reviews">التقرير</a></nav><Bell size={20}/></header>
    <div className="content"><span className="eyebrow">Junior Web Workspace</span><h1 className="title">دورة عمل واحدة، وفريق مترابط.</h1><p className="subtitle">ابدأ باجتماع Manager، ثم نفّذ خمس مهام صغيرة مع Senior. بعد ذلك ينتقل التقرير إلى Manager ثم HR.</p>
      {error && <div className="panel side error flow-message">{error}</div>}

      {data?.project_status === "ready" && <section className="panel kickoff-card"><span className="eyebrow">الخطوة الأولى</span><h2>انضم إلى مشروع Web Developer</h2><p>بعد الانضمام سيشرح Manager المشروع كاملًا، بنيته، المطلوب منك، وآلية الأسبوع قبل ظهور أول مهمة.</p><button className="btn" onClick={() => projectAction("join")} disabled={busy}>{busy ? "جارٍ الانضمام…" : "انضم إلى المشروع"}</button></section>}

      {data?.project_status === "kickoff" && <section className="panel kickoff-card"><span className="eyebrow">اجتماع بداية المشروع · Manager</span><h2>تعريف المشروع قبل العمل</h2><p className="project-overview">{data.project_overview}</p><button className="btn" onClick={() => projectAction("start")} disabled={busy}>{busy ? "جارٍ تجهيز المهمة…" : "فهمت المشروع — ابدأ العمل مع Senior"}</button></section>}

      {data?.project_status === "active" && <>
        {data.notifications[0] && <div className="workspace-alert"><Bell size={16}/><span>{data.notifications[0].body}</span></div>}
        <div className="grid"><section className="panel workspace circle-workspace"><strong className="space-title">دائرة العمل · المهمة {(data.completed_this_week || 0) + 1} من 5</strong><div className="team-ring"/>
          <div className="node manager"><span className="avatar"><Briefcase/></span><strong>Manager</strong><small>يستلم تقرير الأسبوع</small></div>
          <button className="node senior active-agent" onClick={() => setAgent("senior")}><span className="avatar"><Compass/></span><strong>Senior</strong><small>مشرفك المباشر</small></button>
          <div className="node user"><span className="avatar"><UserRound/></span><strong>أنت · Junior</strong><small>تنفذ مهمة واحدة</small></div>
          <div className="node hr"><span className="avatar"><UsersRound/></span><strong>HR</strong><small>التقييم النهائي</small></div>
          <div className="flow-center">Senior → Manager → HR<br/><small>ثم تحديث مستواك</small></div>
        </section>
        <aside className="panel side"><div className="week-progress"><strong>تقدم الأسبوع</strong><span>{data.completed_this_week}/5 مهام</span></div><div className="diagnostic-progress"><span style={{width: `${data.completed_this_week * 20}%`}}/></div>
          <h2 className="section-title task-heading">المهمة الحالية</h2>{task ? <div className="task"><span className="status">{phaseNames[task.status] || task.status}</span><h3>{task.title}</h3><p>{task.brief}</p>
            <div className="lifecycle">{phases.map((phase, index) => <span key={phase} className={`life-step ${index <= phaseIndex ? "active" : ""}`}>{phaseNames[phase]}</span>)}</div>
            <strong>معايير النجاح</strong><ul className="criteria">{task.criteria.map(item => <li key={item}>{item}</li>)}</ul>
            <div className="task-actions">{task.status === "TO_DO" && <button className="btn" onClick={startTask} disabled={busy}>ابدأ المهمة</button>}<button className="btn secondary" onClick={() => setAgent("senior")}>تواصل مع Senior</button></div>
            {(task.status === "IN_PROGRESS" || task.status === "DISCUSSION") && <form className="submission-box" onSubmit={submitTask}><strong>{task.status === "DISCUSSION" ? "إرسال محاولة محسنة" : "تسليم إلى Senior"}</strong><div className="submission-tabs"><button type="button" className={`btn ${submitMode === "code" ? "" : "secondary"}`} onClick={() => setSubmitMode("code")}>اكتب الكود هنا</button><button type="button" className={`btn ${submitMode === "github" ? "" : "secondary"}`} onClick={() => setSubmitMode("github")}>رابط GitHub</button></div>{submitMode === "code" ? <><select name="language" defaultValue="python"><option value="python">Python</option><option value="javascript">JavaScript</option><option value="typescript">TypeScript</option><option value="html">HTML/CSS</option></select><textarea className="code-editor" name="code" required rows={14} dir="ltr" placeholder="# اكتب أو الصق الكود هنا"/></> : <input name="github_url" type="url" required placeholder="رابط GitHub Repository أو Pull Request"/>}<textarea name="summary" minLength={10} required rows={3} placeholder="اشرح ما أنجزته وكيف فكرت في الحل"/><textarea name="challenges" rows={2} placeholder="ما المشكلة أو الجزء غير المكتمل؟"/><button className="btn" disabled={busy}>{busy ? "المودل يحلل المحاولة…" : "أرسل المحاولة إلى Senior"}</button></form>}
            {task.status === "DISCUSSION" && seniorReview && <div className={`review-result ${decision?.outcome}`}><span className="review-badge">{decision?.outcome === "excellent" ? "عمل رائع" : "مناقشة للتحسين"}</span><h3>تحليل Senior الكامل</h3><p>{seniorReview.rationale}</p><div className="review-scores">{Object.entries(seniorReview.scores).map(([name, score]) => <div key={name}><span>{name}</span><strong>{score}/5</strong></div>)}</div>{Boolean(decision?.improvements?.length) && <><strong>التحسينات المقترحة</strong><ul>{decision!.improvements!.map(item => <li key={item}>{item}</li>)}</ul></>}<div className="task-actions">{decision?.outcome === "improve" && <button className="btn secondary" onClick={() => setAgent("senior")}>ناقش Senior</button>}<button className="btn" onClick={closeTask} disabled={busy}>{decision?.outcome === "excellent" ? "انتقل للمهمة التالية" : "اعتمد المراجعة وأنهِ المهمة"}</button></div></div>}
          </div> : <p>جارٍ تجهيز المهمة التالية من Senior…</p>}
        </aside></div>
      </>}

      {data?.weekly_report && <section className="panel side report-flow" id="reviews"><span className="eyebrow">اكتملت الدائرة الأسبوعية</span><h2>Senior → Manager → HR → ملفك الشخصي</h2><div className="evaluation-grid"><article className="evaluation-card"><h4>تقرير Senior</h4><p>{data.weekly_report.senior_report.summary}</p><strong>{data.weekly_report.completed_tasks}/5 مهام</strong></article><article className="evaluation-card"><h4>تقييم Manager التقني</h4><p>{data.weekly_report.manager_evaluation.summary}</p><strong>{data.weekly_report.manager_evaluation.technical_score}/5</strong></article><article className="evaluation-card"><h4>تقييم HR السلوكي</h4><p>{data.weekly_report.hr_evaluation.summary}</p><strong>{data.weekly_report.hr_evaluation.behavior_score}/5</strong></article></div><p>تم تحديث صعوبة ملفك إلى المستوى {data.weekly_report.next_difficulty}/5.</p>{data.project_status === "week_complete" && <button className="btn" onClick={() => projectAction("next-week")} disabled={busy}>ابدأ الأسبوع التالي بالمستوى الجديد</button>}</section>}

      <section className="panel profile-score" id="career"><div><span className="eyebrow">ملف الأداء</span><h2>مستواك الحالي</h2><p>يتحدث تلقائيًا بعد كل أسبوع من التقييم التقني والسلوكي.</p></div><div className="score-circle"><strong>{data?.performance_score ?? 50}</strong><span>/100</span></div></section>
    </div>{agent && <AgentChat agent={agent} onClose={() => {setAgent(null); load();}} taskId={task?.id}/>}</main>;
}
