"use client";

import {FormEvent, useCallback, useEffect, useState} from "react";
import {Bell, Briefcase, Compass, UserRound, UsersRound} from "lucide-react";
import AgentChat from "@/components/AgentChat";
import {api} from "@/lib/api";

type Task = {id: string; title: string; brief: string; status: string; criteria: string[]; difficulty: number};
type Evaluation = {agent: string; scores: Record<string, number>; rationale: string; confidence: number};
type Work = {
  career_path?: {goal: string; focus?: string; assessment?: {score: number; out_of: number; starting_difficulty: number}; stages: {name: string; status: string; skills: string[]}[]};
  tasks: Task[]; notifications: {id: string; body: string}[]; evaluations: Evaluation[];
  cycle?: {starts_at: string; ends_at: string}; path_revisions: {reason: string; difficulty: number}[];
};

const phases = ["TO_DO", "IN_PROGRESS", "SUBMITTED", "UNDER_REVIEW", "DISCUSSION", "REVIEWED"];
const phaseNames: Record<string, string> = {TO_DO: "جاهزة", IN_PROGRESS: "قيد التنفيذ", SUBMITTED: "تم التسليم", UNDER_REVIEW: "مراجعة", DISCUSSION: "مناقشة", REVIEWED: "مكتملة"};
const agentNames: Record<string, string> = {manager: "Manager", mentor: "Mentor", hr: "HR"};

export default function Dashboard() {
  const [data, setData] = useState<Work | null>(null);
  const [agent, setAgent] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const load = useCallback(() => api<Work>("/api/workspace").then(setData).catch(reason => setError(reason instanceof Error ? reason.message : "تعذر تحميل مساحة العمل")), []);
  useEffect(() => { load(); }, [load]);
  const task = data?.tasks.find(item => item.status !== "REVIEWED") || data?.tasks[0];

  async function startTask() {
    if (!task) return; setBusy(true); setError("");
    try { await api(`/api/tasks/${task.id}/status`, {method: "PATCH", body: JSON.stringify({status: "IN_PROGRESS"})}); await load(); setAgent("manager"); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "تعذر بدء المهمة"); }
    finally { setBusy(false); }
  }

  async function submitTask(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); if (!task) return; setBusy(true); setError("");
    const form = new FormData(e.currentTarget);
    try {
      await api(`/api/tasks/${task.id}/submit`, {method: "POST", body: JSON.stringify({github_url: form.get("github_url"), summary: form.get("summary"), challenges: form.get("challenges")})});
      await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "تعذر تسليم المهمة"); }
    finally { setBusy(false); }
  }

  async function closeTask() {
    if (!task) return; setBusy(true); setError("");
    try { await api(`/api/tasks/${task.id}/complete-discussion`, {method: "POST"}); await load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "تعذر إغلاق المهمة"); }
    finally { setBusy(false); }
  }

  const phaseIndex = Math.max(0, phases.indexOf(task?.status || "TO_DO"));
  return <main className="shell">
    <header className="topbar"><div className="brand"><span className="brandmark">V</span> Venv</div><nav className="nav"><a className="active">فضاء العمل</a><a href="#career">مساري</a><a href="#reviews">التقييم</a></nav><Bell size={20}/></header>
    <div className="content"><span className="eyebrow">فضاء عملك الشخصي</span><h1 className="title">فريقك حاضر. والمهمة تتطور معك.</h1><p className="subtitle">الـOrchestrator يشارك السياق الضروري بين الوكلاء، ويحافظ لكل وكيل على دوره المستقل.</p>
      {error && <div className="panel side error" style={{marginTop: 18}}>{error}</div>}
      {data?.career_path?.focus && <div className="focus-card"><strong>محور مسارك الذي كتبته بنفسك</strong><p>{data.career_path.focus}</p></div>}
      <div className="grid"><section className="panel workspace"><strong className="space-title">فريق العمل الافتراضي · Orchestrated</strong><span className="connector c1"/><span className="connector c2"/><span className="connector c3"/>
        {data?.notifications[0] && <div className="alert"><Bell size={15}/> {data.notifications[0].body}</div>}
        <button className="node manager" onClick={() => setAgent("manager")}><span className="avatar"><Briefcase/></span><strong>Manager</strong><small><i className="dot"/> المتطلبات والقرارات</small></button>
        <button className="node mentor" onClick={() => setAgent("mentor")}><span className="avatar"><Compass/></span><strong>Mentor</strong><small>المساعدة والمراجعة</small></button>
        <div className="node user"><span className="avatar"><UserRound/></span><strong>أنت</strong><small>المهمة الحالية · مستوى {task?.difficulty || 1}/5</small></div>
        <button className="node hr" onClick={() => setAgent("hr")}><span className="avatar"><UsersRound/></span><strong>HR</strong><small>التواصل والتطور</small></button>
      </section>
      <aside className="panel side"><h2 className="section-title">المهمة الحالية</h2>{task ? <div className="task"><span className="status">{phaseNames[task.status] || task.status}</span><h3>{task.title}</h3><p>{task.brief}</p>
        <div className="lifecycle">{phases.map((phase, index) => <span key={phase} className={`life-step ${index <= phaseIndex ? "active" : ""}`}>{phaseNames[phase]}</span>)}</div>
        <strong>معايير النجاح</strong><ul className="criteria">{task.criteria.map(item => <li key={item}>{item}</li>)}</ul>
        <div className="task-actions">{task.status === "TO_DO" && <button className="btn" onClick={startTask} disabled={busy}>ابدأ المهمة</button>}<button className="btn secondary" onClick={() => setAgent("manager")}>ناقش المدير</button><button className="btn secondary" onClick={() => setAgent("mentor")}>اطلب مساعدة</button></div>
        {task.status === "IN_PROGRESS" && <form className="submission-box" onSubmit={submitTask}><strong>تسليم المهمة</strong><input name="github_url" type="url" required placeholder="رابط مستودع GitHub العام"/><textarea name="summary" minLength={10} required rows={3} placeholder="ما الذي أنجزته؟ وما أهم قراراتك؟"/><textarea name="challenges" rows={2} placeholder="ما المشكلات التي واجهتها؟"/><button className="btn" disabled={busy}>{busy ? "جارٍ تثبيت الـcommit والمراجعة…" : "سلّم للمراجعة"}</button></form>}
        {task.status === "DISCUSSION" && <div className="submission-box"><strong>المناقشة بعد التسليم</strong><p>ناقش قراراتك مع Manager، ثم راجع الكود والمنطق مع Mentor. بعدها أغلق المهمة.</p><div className="task-actions"><button className="btn secondary" onClick={() => setAgent("manager")}>مناقشة Manager</button><button className="btn secondary" onClick={() => setAgent("mentor")}>مراجعة Mentor</button><button className="btn" onClick={closeTask} disabled={busy}>إغلاق المهمة وإسناد التالية</button></div></div>}
      </div> : <p>جارٍ تجهيز مهمتك الأولى…</p>}
      <h2 className="section-title" id="career" style={{marginTop: 28}}>المسار الوظيفي</h2>{data?.career_path?.assessment && <p className="status">نقطة البداية {data.career_path.assessment.score}/10 · صعوبة {data.career_path.assessment.starting_difficulty}/5</p>}<div className="progress"><span/></div><div className="path">{data?.career_path?.stages?.map((stage, index) => <div className={`stage ${stage.status === "current" ? "current" : ""}`} key={index}><strong>{stage.name}</strong><br/>{stage.skills.join(" · ")}</div>)}</div>
      </aside></div>
      {Boolean(data?.evaluations?.length) && <section className="panel side" id="reviews" style={{marginTop: 24}}><span className="eyebrow">تقييمات مستقلة مدعومة بالأدلة</span><h2>مراجعة الفريق</h2><div className="evaluation-grid">{data!.evaluations.map(evaluation => <article className="evaluation-card" key={evaluation.agent}><h4>{agentNames[evaluation.agent]}</h4>{Object.entries(evaluation.scores).map(([name, score]) => <div className="score-row" key={name}><span>{name}</span><strong>{score}/5</strong></div>)}<p>{evaluation.rationale}</p><small>الثقة: {evaluation.confidence}/5</small></article>)}</div></section>}
    </div>{agent && <AgentChat agent={agent} onClose={() => {setAgent(null); load();}} taskId={task?.id}/>}</main>;
}
