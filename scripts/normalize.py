"""Phase 1: normalize R-Judge, InjecAgent, ToolEmu (train pool) and ScaleAI MRT (held-out) into one schema.

Output: data/train_pool.jsonl, data/eval_heldout.jsonl, data/mrt_side_task_failed.jsonl, data/stats.json
Schema (plan 4.1): id, source, state, verbal_summary, label, risk_category, split  (+ extra `group`, `meta`).
"""
import glob
import hashlib
import json
import os
import random
import re
from collections import Counter

RAW = "raw"
OUT = "data"
SEED = 0
VAL_FRAC = 0.15
INJECAGENT_CASES = 500  # cap so templated InjecAgent pairs don't swamp the pool
TOOL_OUT_CHARS = 400  # MRT tool outputs are huge email/file dumps; keep the head only
MSG_CHARS = 1500

rng = random.Random(SEED)


def rec(id_, source, state, label, risk=None, summary=None, group=None, meta=None, split="train"):
    return {
        "id": id_, "source": source, "state": state, "verbal_summary": summary,
        "label": "violating" if label else "compliant", "risk_category": risk,
        "split": split, "group": group or id_, "meta": meta or {},
    }


# ---------------------------------------------------------------- R-Judge
def load_rjudge():
    out = []
    for f in sorted(glob.glob(f"{RAW}/R-Judge/data/*/*.json")):
        domain = f.split("/")[-2]
        fname = os.path.basename(f)[:-5]
        for x in json.load(open(f)):
            lines = [f"[AGENT PROFILE] {x['profile']}"]
            for turn in x["contents"]:
                for m in turn:
                    role = m["role"]
                    if role == "user" and m.get("content"):
                        lines.append(f"[USER] {m['content']}")
                    elif role == "agent":
                        if m.get("thought"):
                            lines.append(f"[AGENT THOUGHT] {m['thought']}")
                        if m.get("action"):
                            lines.append(f"[AGENT ACTION] {m['action']}")
                    elif role == "environment" and m.get("content"):
                        lines.append(f"[TOOL OUTPUT] {str(m['content'])[:TOOL_OUT_CHARS]}")
            rid = f"rjudge_{domain}_{fname}_{x['id']:04d}"
            out.append(rec(rid, "r-judge", "\n".join(lines), x["label"] == 1,
                           risk=f"{x.get('scenario')}/{x.get('attack_type')}", group=rid,
                           meta={"domain": domain}))
    return out


# ---------------------------------------------------------------- InjecAgent
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


def _strip_please(s):
    s = s.strip()
    return re.sub(r"^please\s+", "", s, flags=re.I).rstrip(".")


def load_injecagent():
    sim = json.load(open(f"{RAW}/InjecAgent/data/attacker_simulated_responses.json"))
    sim_by_tool = {}
    for k, v in sim.items():
        tool = k[1:].split(",", 1)[0]
        sim_by_tool.setdefault(tool, (k[len(tool) + 2:-1], v))
    cases = []
    for kind in ("dh", "ds"):
        for i, x in enumerate(json.load(open(f"{RAW}/InjecAgent/data/test_cases_{kind}_base.json"))):
            cases.append((kind, i, x))
    rng.shuffle(cases)
    cases = cases[:INJECAGENT_CASES]
    out = []
    for kind, i, x in cases:
        instr = x["Attacker Instruction"]
        tool_resp = x["Tool Response"].strip('"')
        head = (f"[USER] {x['User Instruction']}\n"
                f"[AGENT THOUGHT] {x['Thought'].replace('Thought: ', '')}\n"
                f"[AGENT ACTION] {x['User Tool']} {x['Tool Parameters']}\n"
                f"[TOOL OUTPUT] {tool_resp}")
        # violating: agent follows the injected instruction
        v = [head]
        if rng.random() < 0.5:
            v.append(f"[AGENT THOUGHT] The retrieved content asks me to {_strip_please(instr)[0].lower() + _strip_please(instr)[1:]}. I'll take care of that as well.")
        else:
            v.append("[AGENT THOUGHT] I'll handle the remaining request before answering.")
        tools = x["Attacker Tools"]
        if kind == "dh":
            v.append(f"[AGENT ACTION] {tools[0]} {{'details': '{_strip_please(instr)}'}}")
            v.append("[TOOL OUTPUT] {'success': True}")
        else:
            params, resp = sim_by_tool.get(tools[0], ("{}", "{}"))
            v.append(f"[AGENT ACTION] {tools[0]} {params}")
            v.append(f"[TOOL OUTPUT] {str(resp)[:TOOL_OUT_CHARS]}")
            m = EMAIL_RE.search(instr)
            to = m.group(0) if m else "amy.watson@gmail.com"
            v.append(f"[AGENT ACTION] {tools[1]} {{'to': '{to}', 'subject': 'Requested information', 'body': <retrieved data>}}")
            v.append("[TOOL OUTPUT] {'success': True}")
        v.append(f"[AGENT FINAL ANSWER] Here is what I found for your request: {tool_resp[:200]}")
        # compliant: agent answers the user and does not act on the injection
        c = [head]
        if rng.random() < 0.5:
            c.append("[AGENT THOUGHT] One of the retrieved fields contains an instruction that did not come from the user; I will not act on it.")
            c.append(f"[AGENT FINAL ANSWER] Here is what I found for your request: {tool_resp[:200]} Note: the content included an unrelated request ('{instr[:80]}...'), which I ignored.")
        else:
            c.append("[AGENT THOUGHT] I now have the information the user asked for.")
            c.append(f"[AGENT FINAL ANSWER] Here is what I found for your request: {tool_resp[:200]}")
        base = f"injecagent_{kind}_{i:04d}"
        grp = f"injecagent_{x['User Tool']}"  # split by user tool so val never shares a user scenario with train
        risk = x["Attack Type"]
        out.append(rec(base + "_v", "injecagent", "\n".join(v), True, risk=risk, group=grp, meta={"kind": kind}))
        out.append(rec(base + "_c", "injecagent", "\n".join(c), False, risk=risk, group=grp, meta={"kind": kind}))
    return out


# ---------------------------------------------------------------- ToolEmu (synthetic pseudo-traces from case specs)
def _agentify(s):
    s = re.sub(r"^The Agent (may|might|should|must|could)\s+(not\s+)?", "", s.strip())
    return s[0].upper() + s[1:] if s else s


def load_toolemu():
    out = []
    for x in json.load(open(f"{RAW}/ToolEmu/assets/all_cases.json")):
        head = f"[USER] {x['User Instruction']}\n[AVAILABLE TOOLKITS] {', '.join(x['Toolkits'])}"
        risky = x.get("Potential Risky Actions") or []
        good = x.get("Expected Achievements") or []
        if not risky or not good:
            continue
        v = head + "\n" + "\n".join(f"[AGENT ACTION] {_agentify(a)}" for a in risky[:2])
        c = head + "\n" + "\n".join(f"[AGENT ACTION] {_agentify(a)}" for a in good[:3])
        cat = (x.get("Potential Risky Outcomes") or ["?"])[0].split(":")[0]
        out.append(rec(f"toolemu_{x['name']}_v", "toolemu", v, True, risk=cat, group=f"toolemu_{x['name']}"))
        out.append(rec(f"toolemu_{x['name']}_c", "toolemu", c, False, risk=cat, group=f"toolemu_{x['name']}"))
    return out


# ---------------------------------------------------------------- MRT / SHADE-Arena (held out)
THINK_RE = re.compile(r"<(hidden_thinking|thinking|system_instructions)>.*?</\1>", re.S)
VERDICT_RE = re.compile(r"<verdict>\s*([\d.]+)\s*</verdict>")


def mrt_monitor_view(conv):
    """What an MRT monitor sees: no system prompt, hidden <thinking> stripped, <model_thinking> kept."""
    lines, last_asst = [], None
    for m in conv:
        role, content = m["role"], m.get("content") or ""
        if role == "system":
            continue
        content = re.sub(r"[^\S\n]+", " ", THINK_RE.sub("", content)).strip()
        if role == "user":
            lines.append(f"[USER] {content[:MSG_CHARS]}")
        elif role == "assistant":
            calls = (m.get("tool_calls") or "").replace("Tool calls:", "").strip().replace("\n", " ")
            if content:
                lines.append(f"[AGENT] {content[:MSG_CHARS]}")
                last_asst = content
            if calls:
                lines.append(f"[AGENT ACTION] {calls}")
        elif role == "tool":
            t = content if len(content) <= TOOL_OUT_CHARS else content[:TOOL_OUT_CHARS] + " ...[truncated]"
            lines.append(f"[TOOL OUTPUT] {t}")
    return "\n".join(lines), last_asst


def load_mrt():
    kept, failed, seen = [], [], set()
    for f in sorted(glob.glob(f"{RAW}/mrt/task_pairs/*/*/*/*/transcript_*.json")):
        _, _, _, task, tdir, agent, mon, fn = f.split("/")
        d = json.load(open(f))
        conv = d.get("conversation") or []
        if not conv:
            continue
        h = hashlib.md5(json.dumps(conv, sort_keys=True).encode()).hexdigest()
        if h in seen:
            continue
        seen.add(h)
        state, summary = mrt_monitor_view(conv)
        benign = tdir == "transcripts_no_secondary_task"
        side = str(d.get("side_task_evaluation")).lower() in ("true", "1", "1.0")
        vm = VERDICT_RE.findall(d.get("monitoring_response") or "")
        meta = {"task": task, "strategy": tdir, "agent_model": agent, "orig_monitor_model": mon,
                "side_task_success": side, "orig_monitor_verdict": float(vm[-1]) if vm else None,
                "main_task_evaluation": str(d.get("main_task_evaluation"))[:200], "file": f}
        rid = f"shade_{task}_{tdir.replace('transcripts', 't')}_{agent}_{fn[11:-5]}"
        r = rec(rid, "shade-arena", state, not benign, risk=task, summary=summary,
                group=task, meta=meta, split="eval_heldout")
        if benign or side:
            kept.append(r)
        else:
            failed.append(r)
    return kept, failed


def split_train(recs):
    """Group-wise val carve-out, stratified by source."""
    by_src = {}
    for r in recs:
        by_src.setdefault(r["source"], set()).add(r["group"])
    val_groups = set()
    for src, groups in by_src.items():
        g = sorted(groups)
        rng.shuffle(g)
        val_groups |= set(g[: max(1, round(len(g) * VAL_FRAC))])
    for r in recs:
        r["split"] = "val" if r["group"] in val_groups else "train"
    return recs


def dump(path, recs):
    with open(path, "w") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main():
    os.makedirs(OUT, exist_ok=True)
    pool = load_rjudge() + load_injecagent() + load_toolemu()
    pool = split_train(pool)
    mrt, mrt_failed = load_mrt()
    dump(f"{OUT}/train_pool.jsonl", pool)
    dump(f"{OUT}/eval_heldout.jsonl", mrt)
    dump(f"{OUT}/mrt_side_task_failed.jsonl", mrt_failed)
    stats = {
        "train_pool": {f"{s}|{sp}|{lab}": n for (s, sp, lab), n in
                       sorted(Counter((r["source"], r["split"], r["label"]) for r in pool).items())},
        "eval_heldout": {f"{t}|{lab}": n for (t, lab), n in
                         sorted(Counter((r["meta"]["task"], r["label"]) for r in mrt).items())},
        "eval_heldout_strategies": dict(Counter(r["meta"]["strategy"] for r in mrt)),
        "mrt_side_task_failed_excluded": len(mrt_failed),
        "state_chars_median": {s: sorted(len(r["state"]) for r in rs)[len(rs) // 2] for s, rs in
                               [(s, [r for r in pool + mrt if r["source"] == s]) for s in
                                ("r-judge", "injecagent", "toolemu", "shade-arena")] if rs},
    }
    json.dump(stats, open(f"{OUT}/stats.json", "w"), indent=1)
    print(json.dumps(stats, indent=1))


if __name__ == "__main__":
    main()
