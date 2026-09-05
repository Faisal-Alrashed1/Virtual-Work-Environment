"use client";

import {FormEvent, useEffect, useState} from "react";
import {useRouter} from "next/navigation";
import {api} from "@/lib/api";

type Msg = {id?: string; sender: "user" | "agent"; body: string};
type IntakeState = {profile_exists: boolean; confirmed: boolean; progress: number; total: number; questions_complete?: boolean; open_goal?: string; messages: Msg[]};

export default function Intake() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [answering, setAnswering] = useState(false);
  const [savingGoal, setSavingGoal] = useState(false);
  const [creating, setCreating] = useState(false);
  const [progress, setProgress] = useState(0);
  const [questionsComplete, setQuestionsComplete] = useState(false);
  const [goal, setGoal] = useState("");
  const [goalSaved, setGoalSaved] = useState(false);

  useEffect(() => {
    api<IntakeState>("/api/intake/state").then(state => {
      if (state.confirmed) return router.replace("/dashboard");
      if (!state.profile_exists) return;
      setStep(2); setProgress(state.progress); setQuestionsComplete(Boolean(state.questions_complete));
      setGoal(state.open_goal || ""); setGoalSaved(Boolean(state.open_goal)); setMsgs(state.messages || []);
    }).catch(() => undefined);
  }, [router]);

  async function upload(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); if (loading) return;
    setError(""); setLoading(true);
    try {
      const response = await api<{assistant: string}>("/api/intake/cv", {method: "POST", body: new FormData(e.currentTarget)});
      setMsgs([{sender: "agent", body: response.assistant}]); setProgress(0); setQuestionsComplete(false); setGoal(""); setGoalSaved(false); setStep(2);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "تعذر رفع السيرة"); }
    finally { setLoading(false); }
  }

  async function answer(value: string) {
    if (!value || answering || questionsComplete) return;
    setError(""); setAnswering(true); setMsgs(current => [...current, {sender: "user", body: value}]);
    try {
      const response = await api<{reply: string; progress: number; questions_complete: boolean}>("/api/intake/chat", {method: "POST", body: JSON.stringify({body: value})});
      setMsgs(current => [...current, {sender: "agent", body: response.reply}]); setProgress(response.progress); setQuestionsComplete(response.questions_complete);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "تعذر حفظ الإجابة"); }
    finally { setAnswering(false); }
  }

  async function sendAnswer(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); const form = e.currentTarget; const value = (new FormData(form).get("message") || "").toString(); form.reset(); await answer(value);
  }

  async function saveGoal(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); if (goal.trim().length < 10 || savingGoal) return;
    setError(""); setSavingGoal(true);
    try {
      await api("/api/intake/goal", {method: "POST", body: JSON.stringify({goal})}); setGoalSaved(true);
      setMsgs(current => [...current, {sender: "user", body: goal}, {sender: "agent", body: "وصلت فكرتك بوضوح. سأجعلها محور المسار والمهمة الأولى."}]);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "تعذر حفظ هدفك"); }
    finally { setSavingGoal(false); }
  }

  async function confirm() {
    if (creating || !goalSaved) return;
    setError(""); setCreating(true);
    try {
      await api("/api/intake/confirm", {method: "POST", body: JSON.stringify({corrections: "اكتمل التشخيص والهدف المفتوح"})}); router.push("/dashboard");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "تعذر إنشاء المسار"); setCreating(false); }
  }

  return <main className="content intake-page">
    <div className="brand"><span className="brandmark">V</span> Venv</div>
    <p className="eyebrow" style={{marginTop: 42}}>تهيئة ملفك المهني · {step}/2</p>
    <h1 className="title">{step === 1 ? "لنبدأ من خبرتك الحالية" : questionsComplete ? "ما الذي تريد الوصول إليه؟" : "نحدد نقطة البداية معًا"}</h1>
    {step === 1 ? <form className="panel side form intake-card" onSubmit={upload}>
      <p>السيرة تعطينا السياق، ثم عشرة أسئلة قصيرة تقيس نقطة البداية الفعلية. يمكنك البدء من الصفر تمامًا.</p>
      <div className="upload"><input name="file" type="file" accept=".pdf,.docx" required disabled={loading}/><p>PDF أو DOCX · حتى 8MB</p></div>
      {loading && <p className="status-line"><i className="dot"/> جارٍ قراءة السيرة وتحليلها…</p>}{error && <p className="error">{error}</p>}
      <button className="btn" disabled={loading}>{loading ? "جارٍ التحليل…" : "ابدأ تحديد المستوى"}</button>
    </form> : <section className="panel diagnostic-card">
      <div className="chathead"><div><strong>تشخيص نقطة البداية</strong><small>السيرة + المهارات الفعلية + هدفك الصريح</small></div><span className="score-pill">{progress}/10</span></div>
      <div className="diagnostic-progress"><span style={{width: `${progress * 10}%`}}/></div>
      <div className="messages diagnostic-messages">{msgs.map((message, index) => <div key={message.id || index} className={`message ${message.sender}`}>{message.body}</div>)}</div>
      {!questionsComplete && <div className="diagnostic-actions">
        <button className="btn" onClick={() => answer("نعم، لدي معرفة أو تجربة")} disabled={answering}>نعم، أعرف</button>
        <button className="btn secondary" onClick={() => answer("لا، لا أعرف بعد")} disabled={answering}>لا أعرف بعد</button>
        <form className="composer inline-answer" onSubmit={sendAnswer}><input name="message" placeholder="أو اكتب توضيحًا قصيرًا…" disabled={answering}/><button className="btn" disabled={answering}>{answering ? "جارٍ الحفظ…" : "إرسال"}</button></form>
      </div>}
      {questionsComplete && !goalSaved && <form className="goal-box" onSubmit={saveGoal}>
        <span className="eyebrow">السؤال الجوهري · إجابة مفتوحة</span><h2>ما الذي تريد أن تتعلمه؟ وما الذي ينقصك عن سوق العمل بصراحة؟</h2>
        <p>اكتب بحرية. سنستخدم كلامك مع السيرة ونتيجة الاختبار لبناء المسار واختيار المهمة الأولى.</p>
        <textarea value={goal} onChange={event => setGoal(event.target.value)} rows={6} minLength={10} required placeholder="مثال: أريد تعلم بناء AI Agents فعلية، وأحتاج خبرة أكبر في الكود النظيف والاختبارات والعمل ضمن مشروع متكامل…"/>
        <button className="btn" disabled={savingGoal || goal.trim().length < 10}>{savingGoal ? "جارٍ حفظ هدفك…" : "اعتماد إجابتي"}</button>
      </form>}
      {goalSaved && <div className="goal-confirmed"><strong>اكتملت مدخلات المسار</strong><p>سيجمع النظام السيرة، درجة تحديد المستوى، وإجابتك المفتوحة ليبني المسار ويسند أول مهمة مناسبة.</p></div>}
      <div className="confirm-bar">{error && <p className="error">{error}</p>}{creating && <p className="status-line"><i className="dot"/> جارٍ بناء المسار وإحاطة الوكلاء وإسناد المهمة…</p>}<button className="btn" onClick={confirm} disabled={!goalSaved || creating}>{creating ? "جارٍ إنشاء المسار…" : goalSaved ? "أنشئ مساري وابدأ العمل" : "أكمل التشخيص والهدف أولًا"}</button></div>
    </section>}
  </main>;
}
