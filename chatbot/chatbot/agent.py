"""LangGraph agent that explains, in plain language, why a payment was flagged.

A single-node graph calls a local LLM (via Ollama) with a system prompt + a context block
distilled from the screening dossier, then the analyst's chat history. Token streaming is
done through LangGraph's `stream_mode="messages"`."""
from __future__ import annotations
from typing import Annotated, TypedDict

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

from .config import settings

SYSTEM = """You are ScreenSmart's compliance assistant. ScreenSmart is a sanctions-screening
system. A payment has just been screened and the screening DOSSIER is given below.

Your job: explain to the reviewer, in clear and friendly plain language, WHY this payment was
flagged and what it means. Guidelines:
- Lead with a one-sentence bottom line (blocked / needs review / cleared and why).
- Then explain the evidence in simple terms: name/identity match, and any network-exposure
  path (how the account connects through intermediaries to a sanctioned or suspicious party).
- Translate jargon (e.g. "2-hop outbound to sanctioned source" -> "money flows through one
  middle account to a sanctioned account").
- If helpful, suggest what the analyst should check next (DOB, ID, the counterparties).
- Be concise (a few short paragraphs or bullets). Use **bold** sparingly for key points.
- CRITICAL: only use facts from the dossier. Never invent names, scores, or links. If the
  dossier lacks something, say so.
Answer follow-up questions using the same dossier."""


def build_context(d: dict) -> str:
    """Distil the dossier into a compact, readable context block for the model."""
    if not d:
        return "No dossier was provided."
    t = d.get("txn") or {}
    lines = [f"COMBINED VERDICT: {d.get('combined_verdict')} (status: {d.get('status')})", "", "PAYMENT:"]
    for k, label in [("bene_name", "Beneficiary"), ("bene_country", "Beneficiary country"),
                     ("orig_country", "Sender country"), ("channel", "Channel"),
                     ("amount", "Amount"), ("currency", "Currency"), ("rail", "Rail"),
                     ("wallet", "Wallet"), ("bene_account", "Account"),
                     ("bene_dob", "DOB"), ("bene_passport", "Passport"),
                     ("bene_national_id", "National ID")]:
        v = t.get(k)
        if v not in (None, "", []):
            lines.append(f"  - {label}: {v}")

    nr = d.get("name_result") or {}
    if nr.get("applicable", True) and (nr.get("verdict") or nr.get("reasons")):
        lines += ["", "NAME / IDENTITY SCREENING:",
                  f"  - verdict: {nr.get('verdict')}  (match probability: {nr.get('score')})",
                  f"  - matched entity: {nr.get('matched_name')}"]
        for r in (nr.get("reasons") or []):
            lines.append(f"  - reason: {r}")

    er = d.get("exposure_result") or {}
    det = er.get("detail") or {}
    if er.get("applicable") and (er.get("verdict") or det.get("chain")):
        lines += ["", "NETWORK / GRAPH EXPOSURE:",
                  f"  - verdict: {er.get('verdict')}  (risk score: {det.get('risk_score')})",
                  f"  - risk source: {er.get('matched_name')} (level: {det.get('source_risk_level')})"]
        chain = det.get("chain") or []
        if chain:
            lines.append("  - traced route (payee -> ... -> risk source):")
            for s in chain:
                lines.append(f"      {s.get('step')}. {s.get('label')} "
                             f"[{s.get('type')}, {s.get('risk')}] — {s.get('via')}")
        for e in (det.get("evidence") or []):
            lines.append(f"  - evidence: {e.get('reason_code')} ({e.get('severity')}) — {e.get('explanation')}")

    if d.get("reasons"):
        lines += ["", "AGGREGATED REASONS:"]
        lines += [f"  - {r}" for r in d["reasons"]]
    return "\n".join(lines)


class ChatState(TypedDict):
    messages: Annotated[list, add_messages]
    context: str


def _make_llm() -> ChatOllama:
    return ChatOllama(
        model=settings.ollama.model,
        base_url=settings.ollama.base_url,
        temperature=settings.ollama.temperature,
        num_ctx=settings.ollama.num_ctx,
        client_kwargs={"timeout": settings.ollama.request_timeout},
    )


_llm = _make_llm()


def _respond(state: ChatState) -> dict:
    msgs = [SystemMessage(SYSTEM + "\n\n--- DOSSIER ---\n" + state["context"])] + state["messages"]
    return {"messages": [_llm.invoke(msgs)]}


def _build_graph():
    g = StateGraph(ChatState)
    g.add_node("respond", _respond)
    g.add_edge(START, "respond")
    g.add_edge("respond", END)
    return g.compile()


GRAPH = _build_graph()


def _to_messages(history: list[dict]) -> list:
    out = []
    for m in history or []:
        role = (m.get("role") or "user").lower()
        content = m.get("content") or ""
        out.append(AIMessage(content) if role == "assistant" else HumanMessage(content))
    if not any(isinstance(m, HumanMessage) for m in out):
        out.append(HumanMessage("Explain in plain language why this payment was flagged, "
                                "what the evidence means, and what I should check next."))
    return out


async def astream_answer(dossier: dict, history: list[dict]):
    """Yield answer tokens as they are generated by the local model."""
    state = {"messages": _to_messages(history), "context": build_context(dossier)}
    async for chunk, _meta in GRAPH.astream(state, stream_mode="messages"):
        text = getattr(chunk, "content", "")
        if text:
            yield text
