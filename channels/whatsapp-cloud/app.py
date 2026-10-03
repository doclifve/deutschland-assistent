import os,httpx
from fastapi import FastAPI,HTTPException,Query,Request
from fastapi.responses import PlainTextResponse
app=FastAPI(title="Deutschland Assistent WhatsApp Adapter")
CORE=os.getenv("CIVIC_CORE_URL","http://localhost:8000"); VERIFY=os.getenv("WHATSAPP_VERIFY_TOKEN","change-me"); TOKEN=os.getenv("WHATSAPP_ACCESS_TOKEN",""); PHONE=os.getenv("WHATSAPP_PHONE_NUMBER_ID",""); VER=os.getenv("WHATSAPP_GRAPH_VERSION","v22.0")
@app.get("/health")
def health(): return {"status":"ok"}
@app.get("/webhook",response_class=PlainTextResponse)
def verify(hub_mode:str|None=Query(None,alias="hub.mode"),hub_verify_token:str|None=Query(None,alias="hub.verify_token"),hub_challenge:str|None=Query(None,alias="hub.challenge")):
 if hub_mode=="subscribe" and hub_verify_token==VERIFY and hub_challenge:return hub_challenge
 raise HTTPException(403,"Webhook verification failed")
async def send(to,body):
 if not(TOKEN and PHONE):return
 async with httpx.AsyncClient(timeout=20) as c: await c.post(f"https://graph.facebook.com/{VER}/{PHONE}/messages",json={"messaging_product":"whatsapp","to":to,"type":"text","text":{"body":body[:4000]}},headers={"Authorization":f"Bearer {TOKEN}"})
@app.post("/webhook")
async def receive(req:Request):
 p=await req.json()
 try:m=p["entry"][0]["changes"][0]["value"]["messages"][0]; sender=m["from"]; text=m.get("text",{}).get("body")
 except (KeyError,IndexError,TypeError):return {"ok":True,"ignored":True}
 if not text:return {"ok":True,"media_pending":True}
 async with httpx.AsyncClient(timeout=30) as c:r=await c.post(CORE+"/v1/ask",json={"message":text,"language":"de"}); a=r.json()
 lines=[a.get("what_does_it_mean","")]+["• "+x for x in a.get("what_should_i_do",[])[:4]]; await send(sender,"\n\n".join(lines)); return {"ok":True}
