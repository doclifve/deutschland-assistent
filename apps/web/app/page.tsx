"use client";
import { FormEvent, useState } from "react";
const API=process.env.NEXT_PUBLIC_CIVIC_API_URL||"http://localhost:8000";
export default function Home(){
  const [q,setQ]=useState(""); const [answer,setAnswer]=useState<any>(null); const [doc,setDoc]=useState<any>(null); const [busy,setBusy]=useState(false);
  async function ask(e:FormEvent){e.preventDefault(); if(!q.trim())return; setBusy(true); const r=await fetch(API+"/v1/ask",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message:q,language:"de",document_id:doc?.document_id})}); setAnswer(await r.json()); setBusy(false);}
  async function upload(file?:File){if(!file)return;setBusy(true);const f=new FormData();f.append("file",file);const r=await fetch(API+"/v1/documents",{method:"POST",body:f});const d=await r.json();setDoc(d);const a=await fetch(API+"/v1/ask",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message:"Was bedeutet das und was muss ich tun?",document_id:d.document_id,language:"de"})});setAnswer(await a.json());setBusy(false);}
  return <main><section className="hero"><div
          className="project-logo-motion"
          role="img"
          aria-label="Drei Kreise in Schwarz, Rot und Gold, die zeitversetzt auseinander und wieder zusammen atmen, während sich der ganze Cluster langsam dreht."
        >
          <div className="project-logo-cluster">
            <span className="project-logo-circle project-logo-top" />
            <span className="project-logo-circle project-logo-left" />
            <span className="project-logo-circle project-logo-right" />
          </div>
        </div><h1>Deutschland Assistent</h1><p>Dokumente, Gesetze und Verwaltung verständlich machen.</p></section>
  <section className="card"><label className="upload"><strong>Dokument hochladen</strong><span>PDF oder Text · OCR/Scans folgen über Docling</span><input type="file" accept=".pdf,.txt,.md" onChange={e=>upload(e.target.files?.[0])}/></label><div className="or">oder</div><form onSubmit={ask}><textarea value={q} onChange={e=>setQ(e.target.value)} placeholder="z. B. Was bedeutet § 60 SGB I?"/><button disabled={busy}>{busy?"Wird geprüft …":"Frage stellen"}</button></form></section>
  {doc&&<section className="card compact"><strong>{doc.filename}</strong> · {doc.document_type}</section>}
  {answer&&<section className="card result"><div className="eyebrow">Das Wichtigste</div><h2>{answer.what_is_this||"Antwort"}</h2><p>{answer.what_does_it_mean}</p>{answer.deadline&&<div className="deadline"><span>Frist</span><strong>{new Date(answer.deadline.date+"T12:00:00").toLocaleDateString("de-DE")}</strong></div>}<h3>Nächste Schritte</h3><ol>{answer.what_should_i_do?.map((x:string,i:number)=><li key={i}>{x}</li>)}</ol>{answer.sources?.length>0&&<><h3>Offizielle Quellen</h3><div className="sources">{answer.sources.map((s:any,i:number)=><a key={i} href={s.url} target="_blank" rel="noreferrer">{s.title}</a>)}</div></>}<p className="fine">{answer.disclaimer}</p></section>}<footer>Open Source · Quellenorientiert · Werbefrei</footer></main>
}