"use client";

import {FormEvent, useEffect, useState} from "react";
import {api} from "@/lib/api";

type Msg = {id?: string; sender: string; body: string; kind?: string};
const names: Record<string, string> = {manager: "Manager · المدير", mentor: "Mentor · المرشد", hr: "HR · الموارد البشرية"};
const descriptions: Record<string, string> = {
  manager: "يفهم المطلوب، يناقش قراراتك، ويدير المهمة التالية",
  mentor: "يشرح ويلمح أثناء العمل، ثم يراجع الكود والمنطق",
  hr: "يراقب التواصل والمهنية والتطور ويجهز التقرير",
};

export default function AgentChat({agent, onClose, taskId}: {agent: string; onClose: () => void; taskId?: string}) {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { api<Msg[]>(`/api/agents/${agent}/messages`).then(setMsgs).catch(reason => setError(reason instanceof Error ? reason.message : "تعذر تحميل المحادثة")); }, [agent]);
  async function send(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); if (sending) return;
    const form = e.currentTarget; const body = (new FormData(form).get("body") || "").toString(); if (!body) return;
    setError(""); setSending(true); setMsgs(current => [...current, {sender: "user", body}]); form.reset();
    try {
      const response = await api<{reply: string}>(`/api/agents/${agent}/messages`, {method: "POST", body: JSON.stringify({body, task_id: taskId})});
      setMsgs(current => [...current, {sender: "agent", body: response.reply}]);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "تعذر إرسال الرسالة"); }
    finally { setSending(false); }
  }
  return <div className="modal" onClick={onClose}><section className="chat" onClick={event => event.stopPropagation()}><header className="chathead"><div><strong>{names[agent]}</strong><div style={{fontSize: 13, color: "var(--muted)"}}>{descriptions[agent]}</div></div><button className="btn secondary" onClick={onClose}>إغلاق</button></header><div className="messages">{msgs.length === 0 && <div className="message">مرحبًا، أنا مطلع على المسار والمهمة الحالية ضمن حدود دوري. كيف أساعدك؟</div>}{msgs.map((message, index) => <div className={`message ${message.sender}`} key={message.id || index}>{message.kind === "agent_sync" && <small>تحديث من الـOrchestrator<br/></small>}{message.body}</div>)}</div>{error && <p className="error" style={{padding: "0 18px"}}>{error}</p>}<form className="composer" onSubmit={send}><input name="body" placeholder="اكتب رسالتك…" autoFocus disabled={sending}/><button className="btn" disabled={sending}>{sending ? "يفكر…" : "إرسال"}</button></form></section></div>;
}
