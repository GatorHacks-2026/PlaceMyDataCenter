#!/usr/bin/env python3
"""
dc_debate_agents.py - TWO simple LangChain agents TALK about a data-center site (natural conversation), then you get ONE report.

  SENTINEL (the Critic)   : what could go wrong - pollution, resources, noise, community; how many trees would be needed.
  CATALYST (the Advocate) : what is good - jobs, tax base, tech park, future economy, ways to fix the problems.

They only TALK to each other (no tools, no web, no code execution):
  Round 1  each writes an opening from the same facts
  Round 2  each reads the OTHER one's opening and answers it
  Round 3  each writes a short closing (headline + 4 points + one condition)
Code (not the AI) then builds the final report: a 10-second view on top, details below,
and a NUMBER CHECK that flags any number the agents wrote which is not in your facts.

INPUT  : the output of dc_site_report.py (paste the whole printed text, or just its JSON brief, or pass the dict).
CONFIG : OpenAI-compatible endpoint. Key is read from env LLM_API_KEY or asked with a hidden prompt (never stored in this file).

Colab:
    !pip -q install langchain-openai langchain-core
    (run the dc_site_report cell first, then this cell)
"""
from __future__ import annotations

import json
import math
import os
import re

# ----------------------------------------------------------------------------- settings
LLM_CONFIG = dict(base_url="https://api.ai.it.ufl.edu", model="gpt-oss-120b", temperature=0.2, timeout=180, max_retries=2)

# Verified (EPA Greenhouse Gas Equivalencies Calculator, calculations page, Nov 2024 update):
#  - one medium-growth urban tree during its first 10 years absorbs ~0.060 metric tons CO2 per YEAR (36.4 lb C/yr x 44/12)
#  - one acre of average U.S. forest absorbs ~1.00 metric ton CO2 per year (national average; real forests vary)
TREE_T_CO2_PER_YEAR = 0.060
FOREST_T_CO2_PER_ACRE_YEAR = 1.00

# Fill in what you KNOW about local benefits. The Advocate may use ONLY these numbers; None = "not quantified".
ECON = dict(permanent_jobs=None, construction_jobs=None, investment_usd=None, annual_tax_usd=None, tech_park_note=None)

VERDICT_TEXT = {
    "FAVOURABLE": "Looks favourable on the four quick checks",
    "CONDITIONAL": "Possible, with conditions",
    "NOT_AS_PLANNED": "NOT workable as planned",
    "INCOMPLETE": "Incomplete - some checks could not run",
}


# ----------------------------------------------------------------------------- reading the input
def _num(x):
    return float(x.replace(",", ""))


def facts_from_text(text):
    """When only the PLAIN report was pasted (no JSON brief): read verdict, site and key numbers out of its text. Missing pieces stay missing."""
    st = {}
    for key, label in (("power", "Electricity"), ("water", "Water"), ("carbon", "Carbon"), ("noise", "Noise")):
        m = re.search(rf"^\s*\d\.\s+{label}\s+(GREEN|AMBER|RED|NOT CHECKED)", text, re.M)
        if m:
            st[key] = "UNKNOWN" if m.group(1) == "NOT CHECKED" else m.group(1)
    if not st:
        return None
    red = [k for k, v in st.items() if v == "RED"]
    amber = [k for k, v in st.items() if v == "AMBER"]
    unk = [k for k, v in st.items() if v == "UNKNOWN"] + [k for k in ("power", "water", "carbon", "noise") if k not in st]
    code = "NOT_AS_PLANNED" if red else "INCOMPLETE" if unk else "CONDITIONAL" if amber else "FAVOURABLE"
    f = dict(_from_text=True, verdict=dict(code=code, red=red, amber=amber, not_checked=unk), site={}, data_center={},
             comparison=dict(power={}, water={}, carbon={}, noise={}), layers={k: dict(status=v) for k, v in st.items()})
    m = re.search(r"Place:\s*(\w{2}) \(([-\d.]+), ([-\d.]+)\), searched within (\d+) miles", text)
    if m:
        f["site"] = dict(state=m.group(1), lat=float(m.group(2)), lon=float(m.group(3)), radius_miles=int(m.group(4)))
    m = re.search(r"Planned size:\s*([\d.,]+) MW", text)
    if m:
        f["data_center"]["it_mw"] = _num(m.group(1))
    L = f["layers"]
    m = re.search(r"Electricity:\s*about ([\d,.]+) MW on average", text)
    if m: f["comparison"]["power"]["need_mw"] = _num(m.group(1))
    m = re.search(r"(shortfall|spare) (?:of )?about ([\d,.]+) MW", text)
    if m: f["comparison"]["power"]["spare_mw"] = _num(m.group(2)) * (-1 if m.group(1) == "shortfall" else 1)
    m = re.search(r"needs ([\d.]+) MGD|data center needs ([\d.]+) MGD", text)
    if m and "water" in L: L["water"]["need_mgd"] = float(m.group(1) or m.group(2))
    m = re.search(r"In dry periods about ([\d,.]+) MGD", text)
    if m and "water" in L: L["water"]["dry_flow_p10_mgd"] = _num(m.group(1))
    m = re.search(r"= ([\d.]+)% of that", text)
    if m and "water" in L: L["water"]["need_pct_of_dry_flow"] = float(m.group(1))
    m = re.search(r"([\d,]+) metric tons of CO2 a year, like ([\d,]+) cars", text)
    if m and "carbon" in L: L["carbon"].update(total_tco2e_per_year=_num(m.group(1)), cars_equivalent=_num(m.group(2)))
    m = re.search(r"about ([\d.]+) dB at the nearest house \(([\d,]+) m", text)
    if m and "noise" in L: L["noise"].update(continuous_db_at_house=float(m.group(1)), distance_to_house_m=_num(m.group(2)))
    m = re.search(r"Night limit ([\d.]+) dB", text)
    if m and "noise" in L: L["noise"]["night_limit"] = float(m.group(1))
    return f


def load_facts(source):
    """-> (facts dict or None, human report text). Accepts a dict, the JSON brief, or the full printed report.
    If the printed report has no JSON brief, the facts are read from its plain text (facts["_from_text"] = True)."""
    if isinstance(source, dict):
        return source, json.dumps(source, indent=2)
    text = str(source)
    cut = re.search(r"^=+\s*\n(?:DATA CENTER SITE REVIEW|TWO-AGENT)", text, re.M)       # drop an earlier agents' report if it was pasted too
    if cut:
        text = text[:cut.start()].rstrip() + "\n"
    dec = json.JSONDecoder()
    facts = None
    for m in re.finditer(r"\{", text):
        try:
            obj, _ = dec.raw_decode(text[m.start():])
        except ValueError:
            continue
        if isinstance(obj, dict) and "layers" in obj and "verdict" in obj:
            facts = obj
            break
    if facts is None:
        facts = facts_from_text(text)
    return facts, text


def helper_numbers(facts, text) -> dict:
    """Numbers computed by CODE (not by the AI) so both agents use identical figures."""
    t = None
    if facts:
        t = (facts.get("layers", {}).get("carbon", {}) or {}).get("total_tco2e_per_year")
    if t is None:
        m = re.search(r"([\d,]+)\s+metric tons of CO2 a year", text)
        t = float(m.group(1).replace(",", "")) if m else None
    h = {}
    if t:
        h["co2_metric_tons_per_year"] = round(float(t))
        h["trees_needed_to_absorb_one_year_of_emissions"] = round(t / TREE_T_CO2_PER_YEAR)
        h["forest_acres_needed"] = round(t / FOREST_T_CO2_PER_ACRE_YEAR)
        h["forest_square_miles_needed"] = round(t / FOREST_T_CO2_PER_ACRE_YEAR / 640.0)
        h["how_computed"] = ("trees = tons / 0.060 t per tree-year (EPA, medium urban tree, first 10 years); "
                             "forest acres = tons / 1.00 t per acre-year (EPA national average)")
    return h


# ----------------------------------------------------------------------------- agents (plain LangChain chains, no tools)
def make_llm(api_key=None, **over):
    from langchain_openai import ChatOpenAI
    cfg = dict(LLM_CONFIG, **over)
    key = api_key or os.environ.get("LLM_API_KEY")
    if not key:
        from getpass import getpass
        key = getpass("LLM_API_KEY (hidden): ").strip()
    return ChatOpenAI(model=cfg["model"], base_url=cfg["base_url"], api_key=key, temperature=cfg["temperature"],
                      timeout=cfg["timeout"], max_retries=cfg["max_retries"])


RULES = ("RULES: Use ONLY numbers that appear in FACTS, HELPER or ECON below. Never invent statistics, studies, names or prices. "
         "If something is not quantified there, say 'not quantified'. Plain everyday English for a non-expert, short sentences. "
         "Do not repeat the whole report. Do not use tables or markdown headings.")

SENTINEL_SYS = ("You are SENTINEL, the environmental and community CRITIC in a two-agent review of a proposed data center. "
                "Your job: make the strongest honest case for caution - pollution, water, electricity, noise, land, and who is affected. "
                "Include the HELPER numbers about trees/forest when talking about carbon. Be fair: if a check is GREEN, say so; do not exaggerate. " + RULES)
CATALYST_SYS = ("You are CATALYST, the economic BENEFITS advocate in a two-agent review of a proposed data center. "
                "Your job: make the strongest honest case for the project - jobs, tax revenue, a nearby tech park, future computing and economy, "
                "and practical ways to fix the problems found (clean power, reclaimed water, sound walls, distance). "
                "Use ECON numbers ONLY if they are provided; otherwise say the benefit is 'not quantified - needs local data'. "
                "Never deny a RED or AMBER finding; answer it with a fix. " + RULES)

HUMAN = ("TASK: {task}\n\nFACTS (from the site screening; do not contradict):\n{facts}\n\nHELPER (computed by code):\n{helper}\n\n"
         "ECON (provided by the user; None = unknown):\n{econ}\n\n{other}")

TASKS = {
    "open": "ROUND 1 - OPENING. Write your opening argument in 100 words or fewer, as 4 short bullet lines starting with '- '.",
    "rebut": ("ROUND 2 - REBUTTAL. Read the OTHER agent's opening below. In 80 words or fewer, as 3 short bullet lines starting with '- ': "
              "concede what they got right, then answer the strongest point with facts."),
    "close": ("ROUND 3 - CLOSING. Output EXACTLY this format and nothing else:\n"
              "HEADLINE: <at most 12 words>\n- <point, at most 12 words>\n- <point, at most 12 words>\n- <point, at most 12 words>\n"
              "- <point, at most 12 words>\nASK: <one condition or next step, at most 14 words>\n"
              "Put your single strongest point FIRST. Use the other agent's rebuttal below to sharpen it."),
}


class Agent:
    """One role + one LLM. say() = one chain call. No tools, no memory except what the loop passes in."""

    def __init__(self, name, system, llm):
        from langchain_core.output_parsers import StrOutputParser
        from langchain_core.prompts import ChatPromptTemplate
        self.name = name
        self.chain = ChatPromptTemplate.from_messages([("system", system), ("human", HUMAN)]) | llm | StrOutputParser()

    def say(self, task, facts_text, helper_text, econ_text, other=""):
        last = None
        for _ in range(2):
            try:
                out = self.chain.invoke(dict(task=TASKS[task], facts=facts_text, helper=helper_text, econ=econ_text, other=other))
                if out and out.strip():
                    return out.strip()
            except Exception as ex:                             # noqa: BLE001 - report, do not crash the whole debate
                last = ex
        raise RuntimeError(f"{self.name} could not get an answer from the model: {type(last).__name__ if last else 'empty reply'}: {str(last)[:200]}")


# ----------------------------------------------------------------------------- parsing + checks
def _clean_line(s):
    s = re.sub(r"[*_`#]+", "", s).strip()
    return re.sub(r"^\s*(?:[-••]|\d+[.)])\s*", "", s).strip()


def trim_words(s, n):
    w = s.split()
    return s if len(w) <= n else " ".join(w[:n]).rstrip(",;:") + "..."


def parse_closing(text, point_words=12):
    head, pts, ask = "", [], ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        low = re.sub(r"[*_`#]+", "", line).lower()
        if low.startswith("headline"):
            head = _clean_line(re.sub(r"(?i)^\W*headline\W*", "", re.sub(r"[*_`#]+", "", line)))
        elif low.startswith("ask"):
            ask = _clean_line(re.sub(r"(?i)^\W*ask\W*", "", re.sub(r"[*_`#]+", "", line)))
        elif re.match(r"^\s*(?:[-••*]|\d+[.)])\s+", line):
            pts.append(_clean_line(line))
    if not pts:                                                  # model ignored the format: fall back to sentences
        sents = [x.strip() for x in re.split(r"(?<=[.!?])\s+", re.sub(r"[*_`#]+", "", text)) if x.strip()]
        head = head or (sents[0] if sents else "")
        pts = sents[1:5]
    return dict(headline=trim_words(head, 14), points=[trim_words(p, point_words + 4) for p in pts[:4]], ask=trim_words(ask, 18))


_NUM = re.compile(r"(?<![\w.])(\d[\d,]*(?:\.\d+)?)\s*(million|billion|thousand|k\b)?", re.I)


def numbers_in(text):
    out = []
    for m in _NUM.finditer(text):
        try:
            v = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        mult = {"million": 1e6, "billion": 1e9, "thousand": 1e3, "k": 1e3}.get((m.group(2) or "").lower(), 1.0)
        out.append((m.group(0).strip(), v * mult))
    return out


def _leaves(x):
    if isinstance(x, dict):
        for v in x.values():
            yield from _leaves(v)
    elif isinstance(x, (list, tuple)):
        for v in x:
            yield from _leaves(v)
    elif isinstance(x, bool):
        return
    elif isinstance(x, (int, float)) and math.isfinite(x):
        yield float(x)
    elif isinstance(x, str):
        for _, v in numbers_in(x):
            yield v


def number_check(agent_texts, facts, helper, econ, report_text=""):
    """Numbers the agents wrote that cannot be found (within 3%) in the facts. Small whole numbers and years are ignored."""
    allowed = set(_leaves(facts or {})) | set(_leaves(helper)) | set(_leaves(econ)) | {v for _, v in numbers_in(report_text)}
    allowed |= {45.0, 55.0, 6.0, 10.0}
    allowed |= {a / 1000.0 for a in allowed if a >= 1000}          # 4,480 m may be written as 4.5 km
    bad = []
    for t in agent_texts:
        for raw, v in numbers_in(t):
            if (v == int(v) and v <= 10) or 1900 <= v <= 2100:
                continue
            if not any(abs(v - a) <= 0.03 * max(abs(v), abs(a)) + 0.06 for a in allowed):
                if raw not in bad:
                    bad.append(raw)
    return bad


# ----------------------------------------------------------------------------- the debate
def run_debate(source, llm=None, econ=None, verbose=False) -> dict:
    facts, text = load_facts(source)
    helper = helper_numbers(facts, text)
    econ = dict(ECON, **(econ or {}))
    facts_text = json.dumps(facts, indent=1, ensure_ascii=False) if facts else text
    helper_text, econ_text = json.dumps(helper, indent=1), json.dumps(econ, indent=1)
    llm = llm or make_llm()
    S, C = Agent("SENTINEL", SENTINEL_SYS, llm), Agent("CATALYST", CATALYST_SYS, llm)
    args = (facts_text, helper_text, econ_text)
    log = {}
    log["s_open"] = S.say("open", *args)
    log["c_open"] = C.say("open", *args)
    log["s_rebut"] = S.say("rebut", *args, other="CATALYST'S OPENING:\n" + log["c_open"])
    log["c_rebut"] = C.say("rebut", *args, other="SENTINEL'S OPENING:\n" + log["s_open"])
    log["s_close"] = S.say("close", *args, other="CATALYST'S REBUTTAL:\n" + log["c_rebut"])
    log["c_close"] = C.say("close", *args, other="SENTINEL'S REBUTTAL:\n" + log["s_rebut"])
    if verbose:
        for k, v in log.items():
            print(f"[{k}]\n{v}\n")
    s, c = parse_closing(log["s_close"]), parse_closing(log["c_close"])
    bad = number_check(list(log.values()), facts, helper, econ, text)
    return dict(facts=facts, helper=helper, econ=econ, log=log, sentinel=s, catalyst=c, unverified_numbers=bad,
                report=build_report(facts, helper, econ, log, s, c, bad))


# ----------------------------------------------------------------------------- final report (built by code, not by the AI)
def _g(d, *path, default=None):
    for p in path:
        if not isinstance(d, dict) or p not in d:
            return default
        d = d[p]
    return default if d is None else d


def fact_lines(facts):
    if not facts:
        return ["(facts not found in the input - agents read the pasted text only)"]
    L = facts.get("layers", {})
    def st(k): return _g(L, k, "status", default="?")
    def fmt(v, f=",.0f"):
        return format(v, f) if isinstance(v, (int, float)) else "?"
    out = []
    if st("power") in ("UNKNOWN", "?"):
        out.append(f"Electricity [{st('power')}]: not checked")
    else:
        out.append(f"Electricity [{st('power')}]: needs {fmt(_g(facts, 'comparison', 'power', 'need_mw'))} MW average; "
                   f"area spare in its weakest month {fmt(_g(facts, 'comparison', 'power', 'spare_mw'))} MW")
    w = L.get("water", {})
    out.append(f"Water [{st('water')}]: needs {w.get('need_mgd', '?')} MGD; river dry-period flow {w.get('dry_flow_p10_mgd', '?')} MGD "
               f"({w.get('need_pct_of_dry_flow', '?')}% of it)" if w.get("status") not in (None, "UNKNOWN") else f"Water [{st('water')}]: not checked")
    k = L.get("carbon", {})
    out.append(f"Carbon [{st('carbon')}]: {fmt(k.get('total_tco2e_per_year'))} metric tons CO2 a year (= {fmt(k.get('cars_equivalent'))} cars)"
               if k.get("status") not in (None, "UNKNOWN") else f"Carbon [{st('carbon')}]: not checked")
    n = L.get("noise", {})
    out.append(f"Noise [{st('noise')}]: {n.get('continuous_db_at_house', '?')} dB at the nearest house ({n.get('distance_to_house_m', '?')} m); "
               f"night limit {n.get('night_limit', '?')} dB" if n.get("status") not in (None, "UNKNOWN") else f"Noise [{st('noise')}]: not checked")
    return out


def build_report(facts, helper, econ, log, s, c, bad) -> str:
    W = 92
    code = _g(facts, "verdict", "code", default="INCOMPLETE") if facts else "INCOMPLETE"
    red, amber = _g(facts, "verdict", "red", default=[]), _g(facts, "verdict", "amber", default=[])
    site = facts.get("site", {}) if facts else {}
    dc = facts.get("data_center", {}) if facts else {}
    flag = ""
    if red: flag = " - RED: " + ", ".join(red)
    elif amber: flag = " - watch: " + ", ".join(amber)
    L = ["=" * W, "DATA CENTER SITE REVIEW - TWO-AGENT REPORT", "=" * W,
         f"Site: {site.get('state', '?')} ({site.get('lat', '?')}, {site.get('lon', '?')}), {site.get('radius_miles', '?')} mi   |   "
         f"Size: {dc.get('it_mw', '?')} MW of servers   |   Screening, not a final decision",
         "", "10-SECOND VIEW", "-" * 14,
         f"Verdict       : {VERDICT_TEXT.get(code, code)}{flag}",
         f"Biggest worry : {(s['points'] or [s['headline']])[0]}",
         f"Biggest plus  : {(c['points'] or [c['headline']])[0]}",
         f"To proceed    : {s['ask'] or c['ask']}",
         "", "THE FACTS BOTH AGENTS USED", "-" * 26] + ["  " + x for x in fact_lines(facts)]
    if helper:
        L.append(f"  Offsets (computed by code): {helper['co2_metric_tons_per_year']:,} t CO2/yr would need about "
                 f"{helper['trees_needed_to_absorb_one_year_of_emissions']:,} city trees, or {helper['forest_acres_needed']:,} acres "
                 f"({helper['forest_square_miles_needed']:,} sq mi) of average U.S. forest, absorbing each year.")
    for name, role, d in (("SENTINEL", "the critic", s), ("CATALYST", "the benefits advocate", c)):
        L += ["", f"{name} ({role}) - CLOSING POSITION", "-" * 44, d["headline"]] + [f"  - {p}" for p in d["points"]] + [f"  Condition: {d['ask']}"]
    L += ["", "HOW THEY ARGUED (rounds 1-2)", "-" * 28]
    for key, title in (("s_open", "Sentinel opening"), ("c_open", "Catalyst opening"), ("s_rebut", "Sentinel answers Catalyst"),
                       ("c_rebut", "Catalyst answers Sentinel")):
        L += [f"[{title}]", log[key], ""]
    known = {k: v for k, v in econ.items() if v is not None}
    L += ["NUMBER CHECK", "-" * 12,
          ("All numbers the agents wrote were found in the facts." if not bad else
           "Not found in the facts - treat as UNVERIFIED: " + ", ".join(bad[:12]))]
    L += [("Economic inputs you supplied: " + json.dumps(known)) if known else
          "Jobs / tax / investment numbers: NOT supplied, so the benefits side is qualitative. Fill ECON with local data to quantify it.",
          "Limits: AI text can be wrong. The facts come from the screening script (its guesses are listed in that report); the AI adds no data.",
          "=" * W]
    return "\n".join(L)


# ----------------------------------------------------------------------------- NATURAL CONVERSATION MODE
CHAT_RULES = (
    "HOW TO TALK: You are in a real, friendly-but-honest meeting with one other person. Speak in first person ('I', 'you'), plain everyday English, "
    "3 to 5 short sentences (about 90 words at most). Use the other person's name. React to what they JUST said: agree out loud where they are right "
    "(for example 'You're right about both' or 'Water I'll give you'), push back where they are not, and usually end with ONE direct question or a "
    "concrete condition. Do not repeat a point already made. No bullet points, headings, markdown, quotes around your speech or stage directions. "
    "NUMBERS: copy numbers EXACTLY as they appear in FACTS, HELPER or ECON, with the same unit. Do NOT calculate new numbers, do NOT convert units "
    "(say 4,480 m, not km), do NOT round differently. Use at most three numbers per message. Square miles and acres are different - use the HELPER labels. "
    "NO OUTSIDE CLAIMS: no studies, other projects, prices, job counts or statements about what 'usually' happens. If something is not in FACTS, HELPER "
    "or ECON, say it is not quantified or not checked. Fixes are possibilities ('could', 'would need'), never guarantees. Never deny a RED or AMBER finding. "
    "STYLE EXAMPLE (shape only, not content): \"I'll be straight with you, Catalyst. Two things jumped out: [RED item with its number] and [RED item with its number]. "
    "How do we get past that?\"")
SENT_CHAT = ("You are SENTINEL, a careful environmental and community advocate talking with CATALYST about a proposed data center. "
             "You argue for caution: electricity, water, noise, pollution, and who is affected. For carbon, use the HELPER number of city trees (or forest) "
             "needed to soak up one year of emissions. You are fair: if a check is GREEN you admit it openly. You press on what the report says was "
             "NOT checked or only estimated. You want concrete safeguards (for example a utility capacity letter, an acoustic study) before land is bought. " + CHAT_RULES)
CATA_CHAT = ("You are CATALYST, an economic-benefits advocate talking with SENTINEL about a proposed data center. "
             "You argue the site is worth fixing, not ignoring: jobs, tax revenue, a nearby tech park and the future economy are the prize, and every RED or "
             "AMBER item has a practical fix named in the report (dedicated power supply, clean power, sound wall or distance). Use ECON numbers ONLY if "
             "provided; otherwise say plainly that jobs and tax are not quantified and need local data. You stay honest: you concede real problems and you "
             "say when the site should not go ahead. " + CHAT_RULES)
CHAT_HUMAN = ("FACTS (from the site report; do not contradict):\n{facts}\n\nHELPER (computed by code):\n{helper}\n\n"
              "ECON (provided by the user; None = unknown):\n{econ}\n\nCONVERSATION SO FAR:\n{transcript}\n\nYOUR TURN: {task}\n"
              "Write only what you say aloud, without your name in front.")
FIRST_TASK = {
    "SENTINEL": ("You have just read the site report. Open the conversation: say straight out that you read it, name the two or three biggest problems "
                 "(the RED ones first) with their numbers, and ask how Catalyst gets past them."),
}
MID_TASK = {
    "SENTINEL": ("Reply to what Catalyst just said. Give credit where the report says GREEN, but challenge how easy the 'fixes' are using what the report "
                 "says is NOT checked or only estimated, and raise carbon with the HELPER trees number. Ask or demand something concrete."),
    "CATALYST": ("Reply to what Sentinel just said. Concede the fair points first. Then point to what is genuinely fine in the report and to the fixes the "
                 "report names for the problems. Be honest about what is not quantified. End by asking what would make Sentinel comfortable."),
}
CONDITIONS_TASK = {
    "SENTINEL": ("Reply to Catalyst. State your concrete conditions in order (what must come back before land is bought, using the 'NOT checked' items "
                 "and the report's own estimates) and the one thing you will not accept being waved away."),
    "CATALYST": ("Reply to Sentinel. State the conditions under which you would support going ahead, in order, using the fixes named in the report."),
}
PENULTIMATE_TASK = {
    "SENTINEL": ("Reply to Catalyst. Accept the conditions you can accept, in order, and say plainly under which result the site should NOT go ahead."),
    "CATALYST": ("Reply to Sentinel. Accept the conditions you can accept, in order. Say plainly under which result the site should NOT go ahead as planned, "
                 "and that you would rather learn that early."),
}
LAST_TASK = ("This is the last message. Reply to {other}, say in one or two sentences the order of steps you both now agree on, and name the one "
             "thing you still disagree about.")
BOTTOM_TASK = ("Give your bottom line in ONE sentence of at most 25 words (no preamble, no name). Sentinel: start with 'Not ready' or 'Ready' style verdict "
               "and the main reason. Catalyst: say when the site can work.")


def chat_task(role, i, turns):
    other = "Catalyst" if role == "SENTINEL" else "Sentinel"
    if i == 0:
        return FIRST_TASK.get(role) or MID_TASK[role]
    if i == turns - 1:
        return LAST_TASK.format(other=other)
    if i == turns - 2:
        return PENULTIMATE_TASK[role]
    if i == turns - 3 and turns >= 5:
        return CONDITIONS_TASK[role]
    return MID_TASK[role]


class ChatAgent:
    def __init__(self, name, system, llm):
        from langchain_core.output_parsers import StrOutputParser
        from langchain_core.prompts import ChatPromptTemplate
        self.name = name
        self.chain = ChatPromptTemplate.from_messages([("system", system), ("human", CHAT_HUMAN)]) | llm | StrOutputParser()

    def speak(self, task, facts_text, helper_text, econ_text, transcript):
        last = None
        for _ in range(2):
            try:
                out = self.chain.invoke(dict(task=task, facts=facts_text, helper=helper_text, econ=econ_text,
                                             transcript=transcript or "(nobody has spoken yet)"))
                out = re.sub(r"[*_`#]+", "", (out or "")).strip()
                out = re.sub(r"^\s*(?:SENTINEL|CATALYST)\s*[:\-]\s*", "", out, flags=re.I)
                if out:
                    return out
            except Exception as ex:                             # noqa: BLE001
                last = ex
        raise RuntimeError(f"{self.name} could not get an answer from the model: {type(last).__name__ if last else 'empty reply'}: {str(last)[:200]}")


def run_chat(source, llm=None, econ=None, turns=7, verbose=True) -> dict:
    """Sentinel and Catalyst talk to each other. Each turn the speaker sees the whole conversation so far and answers the other one.
    turns = total number of messages (7 = Sentinel speaks first and last). Then each gives a one-sentence bottom line."""
    facts, text = load_facts(source)
    helper = helper_numbers(facts, text)
    econ = dict(ECON, **(econ or {}))
    facts_text = text if (not facts or facts.get("_from_text")) else json.dumps(facts, indent=1, ensure_ascii=False)
    helper_text, econ_text = json.dumps(helper, indent=1), json.dumps(econ, indent=1)
    llm = llm or make_llm()
    S, C = ChatAgent("SENTINEL", SENT_CHAT, llm), ChatAgent("CATALYST", CATA_CHAT, llm)
    turns = max(2, int(turns))
    convo = []                                                  # list of (name, text)
    def tr(): return "\n\n".join(f"{n}: {t}" for n, t in convo)
    for i in range(turns):
        me, other = (S, C) if i % 2 == 0 else (C, S)
        task = chat_task(me.name, i, turns)
        msg = me.speak(task, facts_text, helper_text, econ_text, tr())
        convo.append((me.name, msg))
        if verbose:
            print(f"{me.name}: {msg}\n")
    bottom = {a.name: a.speak(BOTTOM_TASK, facts_text, helper_text, econ_text, tr()) for a in (S, C)}
    bad = number_check([t for _, t in convo] + list(bottom.values()), facts, helper, econ, text)
    return dict(facts=facts, helper=helper, econ=econ, convo=convo, bottom=bottom, unverified_numbers=bad,
                report=build_chat_report(facts, helper, econ, convo, bottom, bad))


def build_chat_report(facts, helper, econ, convo, bottom, bad) -> str:
    W = 92
    code = _g(facts, "verdict", "code", default="INCOMPLETE") if facts else "INCOMPLETE"
    red, amber = _g(facts, "verdict", "red", default=[]), _g(facts, "verdict", "amber", default=[])
    flag = (" - RED: " + ", ".join(red)) if red else (" - watch: " + ", ".join(amber)) if amber else ""
    site, dc = (facts.get("site", {}), facts.get("data_center", {})) if facts else ({}, {})
    L = ["=" * W, "DATA CENTER SITE REVIEW - SENTINEL vs CATALYST", "=" * W,
         f"Site: {site.get('state', '?')} ({site.get('lat', '?')}, {site.get('lon', '?')}), {site.get('radius_miles', '?')} mi   |   "
         f"Size: {dc.get('it_mw', '?')} MW of servers   |   Screening, not a final decision",
         "", "10-SECOND VIEW", "-" * 14,
         f"Verdict      : {VERDICT_TEXT.get(code, code)}{flag}",
         f"Sentinel says: {bottom['SENTINEL']}",
         f"Catalyst says: {bottom['CATALYST']}",
         "", "THE FACTS THEY USED", "-" * 19] + ["  " + x for x in fact_lines(facts)]
    if helper:
        L.append(f"  Offsets (computed by code): {helper['co2_metric_tons_per_year']:,} t CO2/yr would need about "
                 f"{helper['trees_needed_to_absorb_one_year_of_emissions']:,} city trees, or {helper['forest_acres_needed']:,} acres "
                 f"({helper['forest_square_miles_needed']:,} sq mi) of average U.S. forest, absorbing each year.")
    L += ["", "THE CONVERSATION", "-" * 16]
    for n, t in convo:
        L += [f"{n.title()}: {t}", ""]
    known = {k: v for k, v in econ.items() if v is not None}
    L += ["NUMBER CHECK", "-" * 12,
          ("All numbers they used were found in the facts." if not bad else "Not found in the facts - treat as UNVERIFIED: " + ", ".join(bad[:12])),
          ("Economic inputs you supplied: " + json.dumps(known)) if known else
          "Jobs / tax / investment numbers: NOT supplied, so the benefits side stays qualitative. Fill ECON with local data to quantify it.",
          "Limits: AI text can be wrong; the facts come from the site report and the AI adds no data.", "=" * W]
    return "\n".join(L)


def main(source=None, llm=None, econ=None, turns=7):
    """Paste the site report text into REPORT_TEXT (or pass it), then run. The two agents talk; a 10-second view and the full chat are printed."""
    if source is None:
        g = globals()
        if g.get("REPORT_TEXT"):
            source = g["REPORT_TEXT"]
        elif "ai_brief" in g and "o" in g:
            source = g["ai_brief"](g["o"])
        else:
            raise SystemExit("Paste the site report into REPORT_TEXT (or call main(report_text)).")
    print("Sentinel and Catalyst are talking...\n")
    res = run_chat(source, llm=llm, econ=econ, turns=turns, verbose=False)
    print(res["report"])
    return res


REPORT_TEXT = """============================================================================================
DATA CENTER SITE CHECK - SIMPLE REPORT
============================================================================================
Place: GA (33.749, -84.388), searched within 25 miles
Planned size: 100 MW of servers   [IT_MW given directly = 100 MW]
(Made 2026-10-25 18:06 UTC. This is a quick screening, not a final decision.)

THE ANSWER IN ONE LINE
----------------------
NOT workable as planned. Problem areas: Electricity, Noise. See 'what could fix the problems' below.

WHAT THIS DATA CENTER WILL NEED
-------------------------------
Electricity: about 112 MW on average (140 MW at peak) = 981,000 MWh a year
              roughly the yearly use of 90,900 American homes, i.e. about 0.6% of everything GA uses today
Water      : up to 1.14 million gallons a day (MGD) on the busiest days = 1,141,000 gallons = daily use of about 3,800 homes
              (on an average day about 0.91 MGD)
Carbon     : about 323,000 metric tons of CO2 a year, like 70,300 cars driven for a year
Noise      : about 66 dB at the nearest house (400 m / 1,312 ft away), like busy road traffic or a vacuum cleaner

DOES THE AREA HAVE WHAT IT NEEDS?  (4 checks)
---------------------------------------------
 1. Electricity RED (problem)
    In its weakest month (2025-09) the area uses MORE electricity than it makes (shortfall about 107 MW), so there is no spare power.
    (Only total energy was compared. The real connection capacity must be asked from the electric utility.)
 2. Water       GREEN (fine)
    Biggest nearby river: CHATTAHOOCHEE RIVER ABOVE BEAR CR. In dry periods about 789 MGD flows past. The data center needs 1.14 MGD = 0.14% of that. If only 5% of the dry flow could be taken (39.43 MGD), the need is 0.03 times that amount.
    (Legal right to take river water is a separate question. Only the flow was looked at.)
 3. Carbon      AMBER (be careful)
    Electricity in the GA state grid gives about 324 kg of CO2 per MWh, which is 0.92 times the US average. Yearly total about 323,000 metric tons (of which diesel generators 5,020 metric tons).
    (The color only compares the local power grid with the US average. It is not a legal limit.)
 4. Noise       RED (problem)
    Noise from the always-running machines at the nearest house (400 m / 1,312 ft) is about 66 dB. Day limit 55 dB: fail. Night limit 45 dB: fail. While generators run (about 50 hours a year) it can reach about 65 dB.
    (Machine noise levels are my estimates. Your local rules may differ.)

COMPARISON: WHAT THE DATA CENTER NEEDS vs WHAT THE AREA HAS
------------------------------------------------------------
Resource     Data center needs           Area has                                      Gap         Result
Electricity  112 MW average              -107 MW spare (weakest month)                 -219 MW     RED
Water        1.14 MGD (busiest day)      39.4 MGD usable (5% of dry flow)              +38.3 MGD   GREEN
                                         (river CHATTAHOOCHEE RIVER ABOVE BEAR CR: 789 MGD flows in dry periods)            
Noise        66 dB at the house          night limit 45 dB                             -21 dB      RED
Carbon       323,000 t CO2 per year      no 'available amount': it adds to the air                 AMBER

BEFORE vs AFTER THE DATA CENTER
------------------------------------------------------------
 Electricity : area spare -107 MW  ->  after: short by 219 MW  (there is no spare power)
 Water       : dry-period river flow 789 MGD  ->  data center takes 0.14% of it; the river keeps 99.86%
 Noise       : background at the house 40 dB  ->  after: 66 dB  (+26 dB, several times louder than before)
               noise stays above 45 dB out to about 4,479 m (14,696 ft) from the machines = an area of about 15,575 acres; generators add up to 65 dB while they run
 Carbon      : GA power plants emit about 47,920,000 t CO2/yr  ->  this data center equals 0.7% of that (+323,000 t = 70,300 cars)

ENVIRONMENTAL INDICATORS WE CAN CALCULATE
------------------------------------------------------------
 - River stress: takes 0.14% of the dry-period flow of CHATTAHOOCHEE RIVER ABOVE BEAR CR (an indicator only; fish/habitat limits are not applied).
 - Noise footprint: about 15,575 acres where machine noise exceeds 45 dB (wildlife and neighbours).
 - Climate: about 323,000 metric tons of CO2 a year, of which 5,020 t from diesel generators (50 h/yr).
 - NOT calculated: habitat and wildlife effects, local air pollutants (NOx/particles from generators), land use, light, heat. Those need a formal environmental review.

WHAT COULD FIX THE PROBLEMS
---------------------------
 - Electricity: this area's weakest-month surplus supports at most about 0 MW of servers (about 0 MW to be comfortable). For a bigger center choose another area or ask the utility for a dedicated supply.
 - Carbon: every 10% of clean power you buy removes about 31,800 metric tons of CO2 a year. A cleaner grid area also helps.
 - Noise: you need about 21 dB less at the house (sound wall or earth berm, quieter fans), or put the machines about 4,480 m (14,700 ft) away from the nearest house.

HOW MUCH TO TRUST THIS
----------------------
 - Real data used: electricity from EIA (2024-09 to 2026-08); river flow from USGS (8 gauges); grid emissions from EPA eGRID 2023 table
 - Guesses I filled in because you did not give them: cooling needs 40% extra electricity (PUE 1.4); servers run at 80% of full power on average; 1.8 liters of water per kWh; generators run 50 hours a year; nearest house 400 m away; background noise there today is 40 dB; 5% of the river's dry flow can be taken; 5% electricity lost in the wires; noise limits day 55 / night 45 dB (EPA guidance, not your local law); 0% clean power; 0 dB sound barrier
 - Always a guess: how loud the machines are and how many there are (fans, generators, transformers).

NOT CHECKED AT ALL
--------------------
 - Water rights and permits, groundwater, city water capacity - ask the water utility / state water agency.
 - Peak grid capacity, substation and waiting queue - ask the electric utility for a capacity (will-serve) letter.
 - Local noise law, zoning, flood risk, fiber, land price - ask the county planning office.

WORDS USED
--------------------
MW = power (1 MW is about the average use of 800 US homes). MWh = energy. MGD = million gallons per day. dB = loudness (+10 dB sounds about twice as loud).
Comparisons: EPA typical car 4.6 t CO2/year; EIA average US home 10,791 kWh/year (2022); EPA: family uses over 300 gallons/day.
============================================================================================

============================================================================================
DATA CENTER SITE REVIEW - TWO-AGENT REPORT
============================================================================================
Site: GA (33.749, -84.388), 25 mi   |   Size: 100.0 MW of servers   |   Screening, not a final decision

10-SECOND VIEW
--------------
Verdict       : NOT workable as planned - RED: power, noise
Biggest worry : Grid spare –106 MW vs 112 MW need; cannot power center.
Biggest plus  : Renewable contracts can close 106 MW power gap, enabling 100 MW IT load
To proceed    : Require independent power study and noise mitigation plan before proceeding.

THE FACTS BOTH AGENTS USED
--------------------------
  Electricity [RED]: needs 112 MW average; area spare in its weakest month -107 MW
  Water [GREEN]: needs 1.141 MGD; river dry-period flow 788.5 MGD (0.14% of it)
  Carbon [AMBER]: 323,215 metric tons CO2 a year (= 70,264 cars)
  Noise [RED]: 66.0 dB at the nearest house (400 m); night limit 45.0 dB
  Offsets (computed by code): 323,215 t CO2/yr would need about 5,386,917 city trees, or 323,215 acres (505 sq mi) of average U.S. forest, absorbing each year.

SENTINEL (the critic) - CLOSING POSITION
--------------------------------------------
Power shortage and noise make site unworkable as planned
  - Grid spare –106 MW vs 112 MW need; cannot power center.
  - Noise 66 dB at 400 m exceeds limits by ~22 dB.
  - Emissions 323,215 t CO₂e ≈ 5.4 million trees needed.
  - Water use 1.14 MGD is only 0.14 % of dry river flow.
  Condition: Require independent power study and noise mitigation plan before proceeding.

CATALYST (the benefits advocate) - CLOSING POSITION
--------------------------------------------
Clean Power and Noise Solutions Unlock Data Center Benefits
  - Renewable contracts can close 106 MW power gap, enabling 100 MW IT load
  - Acoustic barriers and siting 4.5 km away meet 45 dB night limit
  - Carbon drops 10% with clean power, saving ~31,800 t CO₂/yr
  - Economic gains (jobs, tax, tech park) not quantified – need local data
  Condition: Proceed to detailed feasibility study including power, noise, and economic analysis

HOW THEY ARGUED (rounds 1-2)
----------------------------
[Sentinel opening]
- Power is red: site needs 112 MW average but the grid shows a 107 MW deficit (‑106.95 MW spare) and a 219 MW gap, so supply cannot meet demand.  
- Noise is red: at the nearest house (400 m) projected sound is 66 dB, exceeding the 55 dB day and 45 dB night limits by about 11‑22 dB, needing ~21 dB reduction.  
- Carbon is amber: yearly emissions 323,215 t CO₂e, equal to 70,264 cars, would require about 5.4 million trees or 505 sq mi of forest to offset.  
- Water is green: peak use 1.14 MGD, only 0.14 % of dry‑flow and far below the 39.4 MGD allowance, but water rights are not checked.

[Catalyst opening]
- The 100‑MW IT load (≈112 MW avg) could power ~90,000 homes and anchor a new tech park, driving future computing and regional growth.  
- Water need is 1.14 MGD versus the river’s median 1,050 MGD, so supply is ample; benefits not quantified.  
- Power shortfall and noise exceed limits, but clean‑energy contracts and sound‑walls or generator relocation can fix them, making the site workable.  
- Jobs, tax revenue and investment are not quantified – local data needed – yet similar 100‑MW projects usually create many permanent and construction jobs and a sizable tax base.

[Sentinel answers Catalyst]
- Water is indeed fine: need 1.14 MGD vs river median 1,050 MGD, only 0.14 % of dry flow.  
- Power and noise cannot be remedied easily: grid spare ‑106.95 MW (gap ‑218.95 MW) and can support 0 MW IT; noise 66 dB at 400 m, 21 dB above limits, needing unrealistic mitigation.  
- The center would add 323,215 t CO₂ / yr – equal to 5,386,917 trees or 505 acres of forest – an amber carbon impact.

[Catalyst answers Sentinel]
- Power red: grid spare is –106.95 MW while average need is 112 MW; water green as shown. Fix: add on‑site renewable or dedicated power purchase to supply the shortfall.  
- Noise red: 66 dB at 400 m exceeds limits by ~22 dB. Fix: install sound‑attenuating walls or move equipment to increase distance to ~4.5 km, cutting >21 dB.  
- Carbon amber: 323,215 t CO₂e/yr (≈70,264 cars). Fix: procure 10 % clean power to save ~31,820 t CO₂/yr; diesel use is only 5,019 t yr. Economic benefits not quantified.

NUMBER CHECK
------------
Not found in the facts - treat as UNVERIFIED: 11, 22, 4.5
Jobs / tax / investment numbers: NOT supplied, so the benefits side is qualitative. Fill ECON with local data to quantify it.
Limits: AI text can be wrong. The facts come from the screening script (its guesses are listed in that report); the AI adds no data.
============================================================================================
"""       # paste the whole site report (text + JSON brief, or just the JSON) between the triple quotes

if __name__ == "__main__":
    main()