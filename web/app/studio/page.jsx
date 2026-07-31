"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ReactFlow, { Background, Controls, Handle, MiniMap, Position } from "reactflow";
import "reactflow/dist/style.css";

/* ------------------------------------------------------------------ */
/* helpers                                                             */
/* ------------------------------------------------------------------ */
const api = async (path, opts) => {
  const r = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
};

const BRANCH_COLORS = ["#f54a00", "#1f5fbf", "#1f7a4d", "#8438b8", "#b3540c", "#0e7f8a"];
const branchColor = (branch, order) =>
  branch === "main" ? "#111110" : BRANCH_COLORS[order.indexOf(branch) % BRANCH_COLORS.length];

const MODALITY_ICON = { image: "▣", video: "▶", audio: "♪", voice: "♪" };

/* ------------------------------------------------------------------ */
/* custom DAG node                                                     */
/* ------------------------------------------------------------------ */
function CommitNode({ data }) {
  if (data.ghost) {
    return (
      <div
        style={{
          width: 172, height: 142, borderRadius: 8,
          border: "1.5px dashed rgba(17,17,16,0.35)",
          background: "rgba(244,244,241,0.6)",
          fontFamily: "var(--font-mono)",
          display: "grid", placeItems: "center", gap: 2,
          color: "rgba(17,17,16,0.45)",
        }}
      >
        <Handle type="target" position={Position.Left} style={{ opacity: 0.3 }} />
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 16 }}>{MODALITY_ICON[data.modality] || "◆"}</div>
          <div style={{ fontSize: 9.5, letterSpacing: "0.06em", textTransform: "uppercase", marginTop: 6 }}>{data.step}</div>
          <div style={{ fontSize: 9, marginTop: 4 }}>generating…</div>
        </div>
        <Handle type="source" position={Position.Right} style={{ opacity: 0.3 }} />
      </div>
    );
  }
  const port = {
    width: 11,
    height: 11,
    background: "var(--paper)",
    border: `2.5px solid ${data.color}`,
    borderRadius: "50%",
  };
  return (
    <div
      style={{
        width: 172,
        borderRadius: 8,
        overflow: "hidden",
        border: `1.5px solid ${data.color}`,
        background: "#f4f4f1",
        fontFamily: "var(--font-mono)",
        boxShadow: data.selected
          ? `0 0 0 2px ${data.color}, 0 10px 24px rgba(17,17,16,0.22)`
          : "0 4px 14px rgba(17,17,16,0.14)",
        opacity: data.reused ? 0.72 : 1,
        transition: "box-shadow 0.15s",
      }}
    >
      <Handle type="target" position={Position.Left} style={port} />
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "6px 10px",
          background: data.color,
          color: "#fff",
          fontSize: 9.5,
          letterSpacing: "0.06em",
          textTransform: "uppercase",
        }}
      >
        <span>{data.step}</span>
        <span>{MODALITY_ICON[data.modality] || "◆"}</span>
      </div>
      {data.ext === "mp4" || data.ext === "webm" ? (
        <video src={data.url} autoPlay loop muted playsInline style={{ width: "100%", height: 96, objectFit: "cover", display: "block" }} />
      ) : data.modality === "image" || data.ext === "gif" ? (
        <img src={data.url} alt="" style={{ width: "100%", height: 96, objectFit: "cover", display: "block" }} />
      ) : (
        <div style={{ height: 96, display: "grid", placeItems: "center", fontSize: 28, color: data.color, background: "#fdfdfb" }}>
          {MODALITY_ICON[data.modality] || "◆"}
        </div>
      )}
      <div style={{ padding: "6px 10px", fontSize: 9.5, color: "rgba(17,17,16,0.6)", display: "flex", justifyContent: "space-between" }}>
        <span>{data.hash.slice(0, 12)}</span>
        {data.reused && <span style={{ color: data.color, fontWeight: 700 }}>reused</span>}
      </div>
      <Handle type="source" position={Position.Right} style={port} />
    </div>
  );
}

const nodeTypes = { commit: CommitNode };

/* ------------------------------------------------------------------ */
/* layout: simple layered layout by topological depth, lane by branch  */
/* ------------------------------------------------------------------ */
const NODE_W = 172, NODE_H = 142;
const COL = 300, ROWH = 176, BRANCH_GAP = 240;

function layoutDag(dag, selectedHash, sparking, outline) {
  const ghostEdges = [];
  const branches = [...new Set(dag.nodes.map((n) => n.branch))];
  const byKey = {};
  dag.nodes.forEach((n) => (byKey[`${n.hash}@${n.branch}`] = n));
  const keyFor = (hash, branch) =>
    byKey[`${hash}@${branch}`] ? `${hash}@${branch}`
      : byKey[`${hash}@main`] ? `${hash}@main` : null;

  const parentsOf = {};
  dag.edges.forEach((e) => {
    const child = `${e.to}@${e.branch}`;
    const parent = keyFor(e.from, e.branch);
    if (byKey[child] && parent) (parentsOf[child] ||= []).push(parent);
  });

  // append-stable rank: depends only on same-branch parents, which are
  // immutable — so a placed node keeps its column forever as the run grows
  const rank = {};
  const getRank = (key, seen = new Set()) => {
    if (rank[key] != null) return rank[key];
    if (seen.has(key)) return 0;
    seen.add(key);
    const me = byKey[key];
    const ps = (parentsOf[key] || []).filter((p) => byKey[p]?.branch === me.branch);
    const r = ps.length ? 1 + Math.max(...ps.map((p) => getRank(p, seen))) : 0;
    rank[key] = r;
    return r;
  };
  dag.nodes.forEach((n) => getRank(`${n.hash}@${n.branch}`));

  // rows fill top-down in ledger order (dag.jsonl order — also stable)
  const nodes = [];
  let xOff = 0;
  for (const b of branches) {
    const branchNodes = dag.nodes.filter((n) => n.branch === b);
    const rows = {};
    let maxRank = 0;
    branchNodes.forEach((n) => {
      const r = rank[`${n.hash}@${n.branch}`] ?? 0;
      maxRank = Math.max(maxRank, r);
      const row = rows[r] ?? 0;
      rows[r] = row + 1;
      nodes.push({
        id: n.id,
        type: "commit",
        position: { x: xOff + r * COL, y: row * ROWH },
        data: {
          ...n,
          color: branchColor(b, branches),
          reused: !!n.reused_from,
          selected: n.hash === selectedHash,
        },
      });
    });
    // remix branches continue to the right of their base
    xOff += (maxRank + 1) * COL + BRANCH_GAP;
  }

  // ---- ghost outline: planned steps appear immediately as placeholders ----
  // committed nodes replace their ghosts one by one, edges included, so the
  // graph is fully connected from the moment planning finishes.
  if (outline && outline.steps?.length) {
    const b = outline.branch || "main";
    const committedSteps = new Set(
      dag.nodes.filter((n) => n.branch === b).map((n) => n.step));
    const byStep = {};
    dag.nodes.filter((n) => n.branch === b).forEach((n) => (byStep[n.step] = n));
    // ranks over the outline graph (stable — fixed at plan time)
    const oRank = {};
    const oGet = (id, seen = new Set()) => {
      if (oRank[id] != null) return oRank[id];
      if (seen.has(id)) return 0;
      seen.add(id);
      const st = outline.steps.find((x) => x.id === id);
      const ps = (st?.depends_on || []).filter((d) =>
        outline.steps.some((x) => x.id === d));
      oRank[id] = ps.length ? 1 + Math.max(...ps.map((d) => oGet(d, seen))) : 0;
      return oRank[id];
    };
    outline.steps.forEach((st) => oGet(st.id));
    // place ghosts in free rows of their rank column, in the running lane
    const laneX = nodes.filter((n) => n.data?.branch === b)
      .reduce((m, n) => Math.min(m, n.position.x), 0) || 0;
    const rows = {};
    nodes.forEach((n) => {
      if (n.data?.branch !== b) return;
      const col = Math.round((n.position.x - laneX) / COL);
      rows[col] = Math.max(rows[col] || 0, Math.round(n.position.y / ROWH) + 1);
    });
    const hasInput = dag.nodes.some((n) => n.branch === b && n.step === "product-input");
    outline.steps.forEach((st) => {
      if (committedSteps.has(st.id)) return;
      const col = oRank[st.id] + (hasInput ? 1 : 0);
      const row = rows[col] || 0;
      rows[col] = row + 1;
      nodes.push({
        id: `ghost@${st.id}`,
        type: "commit",
        position: { x: laneX + col * COL, y: row * ROWH },
        data: { step: st.id, modality: st.modality, branch: b, ghost: true,
                hash: "", color: "rgba(17,17,16,0.35)", url: null },
      });
    });
    // outline edges: dashed toward/from ghosts
    outline.steps.forEach((st) => {
      (st.depends_on || []).forEach((dep, k) => {
        const sNode = byStep[dep] ? byStep[dep].id : `ghost@${dep}`;
        const tNode = byStep[st.id] ? byStep[st.id].id : `ghost@${st.id}`;
        if (byStep[dep] && byStep[st.id]) return; // real edge exists already
        ghostEdges.push({
          id: `ge-${st.id}-${k}`,
          source: sNode,
          target: tNode,
          animated: false,
          style: { stroke: "rgba(17,17,16,0.3)", strokeWidth: 1.5,
                   strokeDasharray: "4 4" },
        });
      });
    });
  }

  // edges bind to exact (hash, branch) nodes — always animated: the ledger is alive
  const edges = dag.edges
    .map((e, i) => {
      const sKey = keyFor(e.from, e.branch);
      const t = byKey[`${e.to}@${e.branch}`];
      if (!sKey || !t) return null;
      return {
        id: `e${i}`,
        source: byKey[sKey].id,
        target: t.id,
        animated: true,
        style: {
          stroke: branchColor(e.branch, branches),
          strokeWidth: sparking ? 2.75 : 2.25,
          strokeOpacity: 0.8,
          strokeLinecap: "round",
          filter: sparking ? "drop-shadow(0 0 4px rgba(245,74,0,0.85))" : "none",
        },
      };
    })
    .filter(Boolean);
  return { nodes, edges: [...edges, ...ghostEdges], branches };
}

/* ------------------------------------------------------------------ */
/* studio page                                                         */
/* ------------------------------------------------------------------ */
export default function Studio() {
  const [user, setUser] = useState(null);
  const [projects, setProjects] = useState([]);
  const [projectId, setProjectId] = useState(null);
  const [dag, setDag] = useState({ nodes: [], edges: [] });
  const [events, setEvents] = useState([]);
  const [running, setRunning] = useState(false);
  const [brief, setBrief] = useState("30-sec teaser for a coffee brand");
  const [branch, setBranch] = useState("main");
  const [baseBranch, setBaseBranch] = useState("");
  const [selected, setSelected] = useState(null); // commit detail
  const [menuOpen, setMenuOpen] = useState(false);
  const [panel, setPanel] = useState(null); // "profile" | "settings" | null
  const [newProjectOpen, setNewProjectOpen] = useState(false);
  const [newProjectName, setNewProjectName] = useState("");
  const [settings, setSettings] = useState({
    gateMin: 7.0,
    autoFailover: true,
    liveNotifications: true,
    theme: "paper",
  });
  const [profileDraft, setProfileDraft] = useState({ name: "", email: "" });
  const [savedFlash, setSavedFlash] = useState("");
  const [works, setWorks] = useState([]);
  const [confirmWork, setConfirmWork] = useState(null); // job_id pending confirm
  const [cycle, setCycle] = useState("monthly");
  const [cancelling, setCancelling] = useState(false);
  const [ents, setEnts] = useState({});
  const [inputAsset, setInputAsset] = useState(null); // uploaded product image
  const [voiceScript, setVoiceScript] = useState("");
  const [planOutline, setPlanOutline] = useState(null); // ghost graph while running
  const [payGate, setPayGate] = useState(null); // paid signup: block studio until pay/skip
  const [payBusy, setPayBusy] = useState(false);
    const [pendingPlan, setPendingPlan] = useState(null);
  const [showDelete, setShowDelete] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  // switching projects: clear the canvas instantly, don't show the old graph
  useEffect(() => {
    projRef.current = projectId;         // sync before any fetch fires
    setDag({ nodes: [], edges: [] });
    setSelected(null);
    setPlanOutline(null);
    // fresh project = fresh form
    setBrief("");
    setVoiceScript("");
    setVoice("");
    setMusicStyle("");
    setNShots("2");
    setVideoSecs("");
    setInputAsset(null);
    if (projectId) refreshDag(projectId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  const [voice, setVoice] = useState("");        // TTS voice choice
  const [musicStyle, setMusicStyle] = useState(""); // music preset or "none"
  const [nShots, setNShots] = useState("2");
  const [videoSecs, setVideoSecs] = useState("");
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef(null);
  const [plan, setPlan] = useState("free");
  const [confirmDelete, setConfirmDelete] = useState(null); // project object
  const wsRef = useRef(null);
  const router = useRouter();

  useEffect(() => {
    (async () => {
      const r = await fetch("/api/auth/me").catch(() => null);
      if (!r || r.status === 401) {
        router.push("/login");
        return;
      }
      const u = await r.json();
      setUser(u);
      setPlan(u.plan || "free");
      setEnts(u.entitlements || {});
      setCycle(localStorage.getItem("genlineage.cycle")
        || (u.billing_cycle === "annual" ? "yearly" : u.billing_cycle) || "monthly");
      setProfileDraft({ name: u.name || "", email: u.email || "" });
      localStorage.setItem("genlineage.user", JSON.stringify(u));
      const s = localStorage.getItem("genlineage.settings");
      if (s) setSettings((prev) => ({ ...prev, ...JSON.parse(s) }));
      const q = new URLSearchParams(window.location.search);
      if (q.get("billing")) setPanel("billing");
      if (q.get("verify") === "ok") { window.history.replaceState({}, "", "/studio"); flash("✓ Email verified  you're all set"); }
      if (q.get("verify") === "expired") { window.history.replaceState({}, "", "/studio"); flash("That verification link expired send a new one from the banner"); }

    
      const intent = q.get("intent");
      if ((intent === "standard" || intent === "premium") && !q.get("tx_ref")) {
        const cyc0 = q.get("cycle");
        if (cyc0) localStorage.setItem("genlineage.cycle", cyc0 === "annual" ? "yearly" : cyc0);
        localStorage.setItem("genlineage.pendingIntent", intent);
        window.history.replaceState({}, "", "/studio");
      }
      // Resolve it: verified → jump straight to the payment modal.
      // Unverified → keep it in state so the gate screen can say why.
      const pendingIntent = localStorage.getItem("genlineage.pendingIntent");
      if (pendingIntent) {
        if (u.email_verified !== false) {
          localStorage.removeItem("genlineage.pendingIntent");
          setPayGate(pendingIntent);
        } else {
          setPendingPlan(pendingIntent);
        }
      }
      if (false) {
        const cyc = q.get("cycle") || localStorage.getItem("genlineage.cycle") || "monthly";
        setPanel("billing");
        flash("Opening secure checkout…");
        try {
          const cr = await fetch("/api/billing/checkout", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ plan: intent, cycle: cyc }),
          });
          const cd = await cr.json();
          if (!cr.ok) throw new Error(cd.detail || "Checkout unavailable");
          window.location.href = cd.link;
          return;
        } catch (e) {
          flash(String(e.message || "Couldn't open checkout — upgrade below"));
        }
      }
      
      const txRef = q.get("tx_ref");
      const txId = q.get("transaction_id");
      if (txRef) {
        window.history.replaceState({}, "", "/studio"); // clean the URL
        if (q.get("status") === "cancelled") {
          flash("Checkout cancelled no charge was made");
          setPanel("billing");
        } else if (txId) {
          const vr = await fetch("/api/billing/verify", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ tx_ref: txRef, transaction_id: txId }),
          });
          const vd = await vr.json().catch(() => ({}));
          if (vr.ok && vd.ok) {
            setPlan(vd.plan);
            setUser((prev) => ({ ...prev, plan: vd.plan }));
            flash(`✓ Payment confirmed welcome to ${vd.plan[0].toUpperCase()}${vd.plan.slice(1)}`);
            setPanel("billing");
          } else {
            flash(vd.detail || "Payment could not be verified contact support");
            setPanel("billing");
          }
        }
      }
      refreshProjects();
    })();
  }, []);

  const uploadImage = async (file) => {
    if (!file) return;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const r = await fetch("/api/uploads", { method: "POST", body: fd });
      if (!r.ok) throw new Error(await r.text());
      setInputAsset(await r.json());
      flash("Product image attached");
    } catch {
      flash("Upload failed — png, jpg or webp up to 10MB");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const cancelSubscription = async () => {
    setCancelling(true);
    try {
      const r = await fetch("/api/billing/cancel", { method: "POST" });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || "Couldn't cancel");
      const me2 = await fetch("/api/auth/me").then((x) => x.json());
      setUser(me2);
      setPlan(me2.plan);
      setEnts(me2.entitlements || {});
      flash("Subscription cancelled — access continues until the period ends");
    } catch (e) {
      flash(String(e.message || "Couldn't cancel subscription"));
    } finally {
      setCancelling(false);
    }
  };

  const loadWorks = async () => setWorks(await api("/works").catch(() => []));

  useEffect(() => {
    if (panel === "works") loadWorks();
  }, [panel]);

  const deleteWork = async (jobId) => {
    await api(`/works/${jobId}`, { method: "DELETE" }).catch(() => null);
    setConfirmWork(null);
    await Promise.all([loadWorks(), refreshProjects()]);
    refreshDag(projectId);
    flash("Work deleted");
  };

  const changePlan = async (next) => {
    try {
      if (next === "free") {
        const r = await fetch("/api/auth/plan", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ plan: "free" }),
        });
        const data = await r.json();
        if (!r.ok) throw new Error(data.detail || "failed");
        setPlan(data.plan);
        setUser(data);
        flash("Downgraded to Free");
        return;
      }
      // paid: create a Flutterwave checkout and hand the user to the hosted page
      const cycle = localStorage.getItem("genlineage.cycle") || "monthly";
      flash("Opening secure checkout…");
      const r = await fetch("/api/billing/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan: next, cycle }),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || "Checkout failed");
      window.location.href = data.link;
    } catch (e) {
      flash(String(e.message || "Couldn't change plan"));
    }
  };

  const flash = (msg) => {
    setSavedFlash(msg);
    setTimeout(() => setSavedFlash(""), 2200);
  };

  const saveProfile = async () => {
    try {
      const r = await fetch("/api/auth/profile", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(profileDraft),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || "failed");
      setUser(data);
      localStorage.setItem("genlineage.user", JSON.stringify(data));
      flash("Profile saved");
    } catch (e) {
      flash(String(e.message || "Couldn't save profile"));
    }
  };

  const saveSettings = (next) => {
    setSettings(next);
    localStorage.setItem("genlineage.settings", JSON.stringify(next));
  };

  const logout = async () => {
    await fetch("/api/auth/logout", { method: "POST" }).catch(() => null);
    localStorage.removeItem("genlineage.user");
    router.push("/login");
  };

  const refreshProjects = async () => {
    const list = await api("/projects").catch(() => []);
    setProjects(list);
    setProjectId((cur) => cur && list.some((p) => p.id === cur) ? cur : (list[0]?.id ?? null));
  };

  const deleteProject = async () => {
    if (!confirmDelete) return;
    await api(`/projects/${confirmDelete.id}`, { method: "DELETE" }).catch(() => null);
    setConfirmDelete(null);
    setSelected(null);
    await refreshProjects();
    flash("Project deleted");
  };

  const [dagLoading, setDagLoading] = useState(false);
  const projRef = useRef(null);
  const fetchSeq = useRef(0);
  useEffect(() => { projRef.current = projectId; }, [projectId]);
  const refreshDag = useCallback(async (pid) => {
    // always refresh the CURRENT project — stale closure args must not
    // skip a refresh (that wiped the canvas mid-run) or paint an old one
    if (pid) projRef.current = pid;      // explicit id wins — never fetch stale
    const want = pid || projRef.current;
    if (!want) { setDag({ nodes: [], edges: [] }); return; }
    const seq = (fetchSeq.current = (fetchSeq.current || 0) + 1);
    setDagLoading(true);
    const d = await api(`/projects/${want}/dag`).catch(() => ({ nodes: [], edges: [] }));
    // superseded by a newer fetch: that one owns the loading flag now. Leaving
    // it set is what stops "EMPTY DAG" flashing before the real graph lands.
    if (seq !== fetchSeq.current) return;
    if (want === projRef.current) setDag(d);
    setDagLoading(false);
  }, []);

  // NOTE: the project-switch effect above is the single place that triggers a
  // refresh on projectId change. A second effect here would race it — the
  // loser resolved first and blanked the canvas mid-load.

  const createProject = async () => {
    const name = newProjectName.trim();
    if (!name) return;
    try {
      const p = await api("/projects", { method: "POST", body: JSON.stringify({ name }) });
      await refreshProjects();
      setProjectId(p.id);
      setNewProjectName("");
      setNewProjectOpen(false);
    } catch (e) {
      flash(String(e.message || e).replace(/^\d+\s*/, "").replace(/[{}"]|detail:/g, "").trim() || "Plan limit reached");
    }
  };

  const runJob = async () => {
    if (!projectId || running) return;
    setEvents([]);
    setRunning(true);
    let job;
    try {
      job = await api(`/projects/${projectId}/jobs`, {
      method: "POST",
      body: JSON.stringify({
        brief,
        branch: branch || "main",
        base_branch: (baseBranch && baseBranch !== (branch || "main")) ? baseBranch : null,
        gate_min: settings.gateMin,
        input_hash: inputAsset?.hash || null,
        input_ext: inputAsset?.ext || null,
        voice_script: voiceScript.trim() || null,
        voice: voice || null,
        music_style: musicStyle || null,
        n_shots: parseInt(nShots, 10) || null,
        video_secs: videoSecs ? parseInt(videoSecs, 10) : null,
      }),
      });
    } catch (e) {
      setRunning(false);
      flash(String(e.message || e).replace(/^\d+\s*/, "").replace(/[{}"]|detail:/g, "").trim() || "Plan limit reached");
      return;
    }
    // Vercel does not proxy WebSockets, so the /ws rewrite in next.config.mjs
    // only works locally. In production set NEXT_PUBLIC_GENLINEAGE_WS to the
    // backend origin and we connect to it directly.
    //
    // The socket is authenticated with a short-lived, single-use ticket: the
    // session cookie is SameSite=Lax and is NOT sent on a cross-site handshake,
    // so we mint the ticket over the ordinary same-origin API call first.
    let ticket = null;
    try {
      const tr = await fetch("/api/ws-ticket", { method: "POST" });
      if (tr.ok) ticket = (await tr.json()).ticket;
    } catch {
      /* same-origin dev still authenticates via the cookie */
    }
    const wsBase = (process.env.NEXT_PUBLIC_GENLINEAGE_WS || "")
      .trim().replace(/\/+$/, "").replace(/^http/, "ws");
    const qs = ticket ? `?ticket=${encodeURIComponent(ticket)}` : "";
    const wsUrl = wsBase
      ? `${wsBase}/ws/jobs/${job.id}${qs}`
      : `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/jobs/${job.id}${qs}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;
    ws.onmessage = (m) => {
      const e = JSON.parse(m.data);
      if (settings.liveNotifications) setEvents((prev) => [...prev.slice(-120), e]);
      if (e.event === "plan.done" && e.steps) setPlanOutline({ branch, steps: e.steps });
      if (e.event === "step.commit" || e.event === "step.reused") refreshDag(projectId);
      if (e.event === "job.done" && job?.id) {
        fetch(`/api/jobs/${job.id}`).then((r) => r.json()).then((jd) => {
          if (jd?.total_cost_usd != null) flash(`Run complete — total cost $${jd.total_cost_usd.toFixed(2)}`);
          else flash("Run complete");
        }).catch(() => {});
      }
      if (e.event === "job.done" || e.event === "job.failed") {
        setPlanOutline(null);
        setRunning(false);
        if (!settings.liveNotifications) setEvents([e]); // still surface the outcome
        refreshProjects();
      }
    };
    ws.onclose = (ev) => {
      setRunning(false);
      // 4401 not authenticated · 4403 not your job — otherwise the feed would
      // just go quiet with no explanation
      if (ev?.code === 4401 || ev?.code === 4403) {
        flash("Live feed disconnected — reload the page and sign in again");
      }
    };
  };

  const openCommit = async (node) => {
    const detail = await api(`/commits/${node.data.hash}`).catch(() => null);
    setSelected(detail);
  };

  const { nodes, edges, branches } = useMemo(
    () => layoutDag(dag, selected?.hash, running, planOutline),
    [dag, selected, running, planOutline]
  );

  // The actual gate — nothing dashboard-shaped renders past this point
  // until the account is verified.
  if (user && user.email_verified === false) {
    return (
      <div style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: 24 }}>
        <div className="mono" style={{ maxWidth: 420, width: "100%", textAlign: "center", display: "grid", gap: 16, padding: 28, border: "1px solid var(--line-strong)", background: "var(--paper)" }}>
          <img src="/logo.png" alt="" style={{ width: 34, margin: "0 auto" }} />
          <b style={{ fontSize: 15 }}>
            {pendingPlan
              ? `Verify your email to continue with your ${pendingPlan[0].toUpperCase()}${pendingPlan.slice(1)} subscription`
              : "Verify your email to continue"}
          </b>
          <p className="dim" style={{ fontSize: 11.5, lineHeight: 1.6, margin: 0 }}>
            {pendingPlan
              ? <>We sent a link to <b>{user.email}</b>. Click it to verify your account you'll come straight back here to finish setting up {pendingPlan[0].toUpperCase()}{pendingPlan.slice(1)}.</>
              : <>We sent a link to <b>{user.email}</b>. Click it to unlock your studio nothing else works until then.</>}
          </p>
          <button className="btn solid" style={{ justifyContent: "center" }}
            onClick={async () => {
              const r = await fetch("/api/auth/verify/send", { method: "POST" });
              flash(r.ok ? "Verification email sent check your inbox" : "Couldn't send just now");
            }}>
            Resend verification email
          </button>
          <button className="btn" style={{ justifyContent: "center" }} onClick={logout}>Log out</button>
          {savedFlash && <p className="mono" style={{ fontSize: 11 }}>✓ {savedFlash}</p>}
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: "grid", gridTemplateRows: "var(--nav-h) 1fr", height: "100vh", overflow: "hidden" }}>
      {!sidebarOpen && !selected && (
        <button className="gl-burger mono" aria-label="Open pipeline panel" onClick={() => setSidebarOpen(true)}>
          ☰<span style={{ fontSize: 10, letterSpacing: "0.08em" }}>PIPELINE</span>
        </button>
      )}
      {sidebarOpen && <div className="gl-drawer-backdrop" onClick={() => setSidebarOpen(false)} />}
      {showDelete && (
        <div style={{ position: "fixed", inset: 0, zIndex: 90, background: "rgba(17,17,16,0.55)", display: "grid", placeItems: "center", padding: 20 }} onClick={() => !deleting && setShowDelete(false)}>
          <div className="mono" onClick={(e) => e.stopPropagation()} style={{ width: 380, maxWidth: "100%", background: "var(--paper)", border: "1px solid var(--line-strong)", padding: 24, display: "grid", gap: 14, textAlign: "center" }}>
            <img src="/logo.png" alt="" style={{ width: 34, margin: "0 auto" }} />
            <b style={{ fontSize: 15, color: "var(--accent)" }}>Delete account permanently</b>
            <p className="dim" style={{ fontSize: 11.5, lineHeight: 1.6, margin: 0 }}>
              Every project, commit, work and signed manifest you own will be erased.
              This cannot be undone.
            </p>
            <button className="btn solid" style={{ justifyContent: "center", background: "var(--accent)", borderColor: "var(--accent)" }} disabled={deleting}
              onClick={async () => {
                setDeleting(true);
                const r = await fetch("/api/auth/delete-account", { method: "POST" });
                if (r.ok) { localStorage.clear(); window.location.href = "/"; }
                else { setDeleting(false); setShowDelete(false); flash("Couldn't delete the account just now"); }
              }}>
              {deleting ? "Deleting…" : "Yes, delete everything"}
            </button>
            <button className="btn" style={{ justifyContent: "center" }} disabled={deleting} onClick={() => setShowDelete(false)}>
              Cancel
            </button>
          </div>
        </div>
      )}
      {payGate && (
        <div style={{ position: "fixed", inset: 0, zIndex: 80, background: "var(--paper)", display: "grid", placeItems: "center" }}>
          <div className="mono" style={{ maxWidth: 400, textAlign: "center", display: "grid", gap: 14, padding: 24, border: "1px solid var(--line-strong)", background: "var(--paper)" }}>
            <img src="/logo.png" alt="" style={{ width: 34, margin: "0 auto" }} />
            <b style={{ fontSize: 14 }}>Finish your {payGate} subscription</b>
            <span className="dim" style={{ fontSize: 11.5, lineHeight: 1.6 }}>Your account is ready complete payment to unlock {payGate}, or continue on the Free plan.</span>
            <button className="btn solid" style={{ justifyContent: "center" }} disabled={payBusy}
              onClick={() => { setPayBusy(true); changePlan(payGate); }}>
              {payBusy ? "Opening secure checkout…" : "Pay securely with Flutterwave"}
            </button>
            <button className="btn" style={{ justifyContent: "center" }} onClick={() => { setPayGate(null); flash("You're on the Free plan upgrade any time in Billing"); }}>Continue on Free</button>
          </div>
        </div>
      )}
      {/* top bar */}
      <header style={{ borderBottom: "1px solid var(--line-strong)", display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 20px", background: "var(--paper)" }}>
        <Link href="/studio" className="mono" style={{ fontSize: 13, fontWeight: 700, display: "inline-flex", alignItems: "center", gap: 8 }}>
          <img src="/logo.png" alt="" style={{ width: 26, height: 26, objectFit: "contain" }} />
          <span>GEN<span style={{ color: "var(--accent)" }}>_</span>LINEAGE <span className="dim">/ studio</span></span>
        </Link>
        <div style={{ display: "flex", gap: 14, alignItems: "center", marginLeft: 18, paddingLeft: 18, borderLeft: "1px solid var(--line)" }}>
          {branches?.filter((b) => b).map((b) => (
            <span key={b} className="mono" style={{ fontSize: 11, display: "inline-flex", alignItems: "center", gap: 6 }}>
              <i style={{ width: 8, height: 8, background: branchColor(b, branches), display: "inline-block" }} />
              {b}
            </span>
          ))}

          {/* profile menu */}
          <div style={{ position: "relative" }}>
            <button
              onClick={() => setMenuOpen((v) => !v)}
              style={{
                display: "flex", alignItems: "center", gap: 8, background: "transparent",
                border: "1px solid var(--line-strong)", padding: "5px 10px 5px 6px", borderRadius: 2,
              }}
            >
              <span
                aria-hidden
                style={{
                  width: 24, height: 24, borderRadius: "50%", background: "var(--accent)",
                  color: "#fff", display: "grid", placeItems: "center",
                  fontFamily: "var(--font-mono)", fontSize: 11, fontWeight: 700,
                }}
              >
                {(user?.name || "G").slice(0, 1).toUpperCase()}
              </span>
              <span className="mono" style={{ fontSize: 11.5 }}>{user?.name}</span>
              <span className="dim" style={{ fontSize: 9 }}>▼</span>
            </button>

            {menuOpen && (
              <>
                <div style={{ position: "fixed", inset: 0, zIndex: 60 }} onClick={() => setMenuOpen(false)} />
                <div
                  className="mono"
                  style={{
                    position: "absolute", right: 0, top: "calc(100% + 8px)", zIndex: 61,
                    width: 230, background: "var(--panel)", border: "1px solid var(--line-strong)",
                    boxShadow: "6px 6px 0 rgba(17,17,16,0.12)",
                  }}
                >
                  <div style={{ padding: "14px 14px", borderBottom: "1px solid var(--line)" }}>
                    <div style={{ fontSize: 12.5, fontWeight: 700 }}>{user?.name}</div>
                    <div className="dim" style={{ fontSize: 11, marginTop: 3 }}>{user?.email || "no email set"}</div>
                    <div style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
                      <span className="tag" style={{ fontSize: 9, borderColor: "var(--accent)", color: "var(--accent)" }}>
                        {plan === "standard" ? "Standard plan" : plan === "premium" ? "Premium plan" : "Free plan"}
                      </span>
                      {user?.via === "google" && <span className="tag" style={{ fontSize: 9 }}>Google account</span>}
                    </div>
                  </div>
                  {[
                    ["Profile", () => { setPanel("profile"); setMenuOpen(false); }],
                    ["My works", () => { setPanel("works"); setMenuOpen(false); }],
                    ["Billing", () => { setPanel("billing"); setMenuOpen(false); }],
                    ["Settings", () => { setPanel("settings"); setMenuOpen(false); }],
                    ["Support", () => { window.location.href = "/support"; }],
                  ].map(([label, fn]) => (
                    <button key={label} onClick={fn} style={{ width: "100%", textAlign: "left", padding: "11px 14px", background: "transparent", border: 0, borderBottom: "1px solid var(--line)", fontSize: 12 }}>
                      {label}
                    </button>
                  ))}
                  <button onClick={logout} style={{ width: "100%", textAlign: "left", padding: "11px 14px", background: "transparent", border: 0, fontSize: 12, color: "var(--accent)" }}>
                    Log out
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </header>

      <div style={{ display: "grid", gridTemplateColumns: "300px 1fr auto", minHeight: 0 }}>
        {/* left: control panel */}
        <aside className={`gl-sidebar${sidebarOpen ? " open" : ""}`} style={{ borderRight: "1px solid var(--line-strong)", padding: 18, overflowY: "auto", background: "var(--paper)", display: "grid", gap: 20, alignContent: "start" }}>
          <button className="gl-drawer-close mono" onClick={() => setSidebarOpen(false)}>✕ CLOSE PANEL</button>
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span className="eyebrow">Projects</span>
              <button className="btn" style={{ padding: "4px 10px", fontSize: 10 }} onClick={() => setNewProjectOpen(true)}>+ New</button>
            </div>
            {newProjectOpen && (
              <div style={{ display: "flex", gap: 6, marginTop: 10 }}>
                <input
                  autoFocus
                  placeholder="Project name"
                  value={newProjectName}
                  onChange={(e) => setNewProjectName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") createProject();
                    if (e.key === "Escape") { setNewProjectOpen(false); setNewProjectName(""); }
                  }}
                  style={{ padding: "8px 10px", fontSize: 12, flex: 1, minWidth: 0 }}
                />
                <button className="btn solid" style={{ padding: "6px 10px", fontSize: 11 }} onClick={createProject} disabled={!newProjectName.trim()}>✓</button>
                <button className="btn" style={{ padding: "6px 10px", fontSize: 11 }} onClick={() => { setNewProjectOpen(false); setNewProjectName(""); }}>×</button>
              </div>
            )}
            <div style={{ display: "grid", gap: 6, marginTop: 12 }}>
              {projectId && (
                <button className="mono" onClick={() => setProjectId(null)}
                  style={{ fontSize: 9.5, padding: "3px 8px", border: "1px solid var(--line-strong)", background: "transparent", color: "var(--ink-60)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 8 }}>
                  Close project ×
                </button>
              )}
              {/* only the active project lives here — previous ones are in My Works */}
              {projects.filter((p) => p.id === projectId).map((p) => (
                <div
                  key={p.id}
                  className="mono"
                  style={{
                    display: "flex", alignItems: "center", gap: 6,
                    border: "1px solid " + (p.id === projectId ? "var(--ink)" : "var(--line)"),
                    background: p.id === projectId ? "var(--panel)" : "transparent",
                  }}
                >
                  <button
                    onClick={() => setProjectId(p.id)}
                    className="mono"
                    style={{ flex: 1, textAlign: "left", padding: "10px 12px", fontSize: 12, background: "transparent", border: 0 }}
                  >
                    {p.name}
                    <span className="dim" style={{ float: "right" }}>{p.commits}</span>
                  </button>
                  <button
                    onClick={() => setConfirmDelete(p)}
                    aria-label={`Delete ${p.name}`}
                    title="Delete project"
                    className="dim"
                    style={{ padding: "10px 10px", background: "transparent", border: 0, fontSize: 12, lineHeight: 1 }}
                  >
                    ×
                  </button>
                </div>
              ))}
              {!projects.length && <p className="mono dim" style={{ fontSize: 12 }}>No projects yet. Create one to start committing.</p>}
            </div>
          </div>

          {ents.audit_export && projectId && (
            <a
              className="btn"
              style={{ justifyContent: "center", fontSize: 10 }}
              href={`/api/projects/${projectId}/audit`}
              download
            >
              Export audit bundle ↓
            </a>
          )}

          <div style={{ display: "grid", gap: 12 }}>
            <span className="eyebrow orange">New pipeline run</span>
            <div style={{ display: "grid", gap: 6 }}>
              <label>Product image (optional)</label>
              <input
                ref={fileRef}
                type="file"
                accept="image/png,image/jpeg,image/webp"
                style={{ display: "none" }}
                onChange={(e) => uploadImage(e.target.files?.[0])}
              />
              {inputAsset ? (
                <div style={{ display: "flex", alignItems: "center", gap: 10, border: "1px solid var(--line-strong)", background: "#fdfdfb", padding: 8 }}>
                  <img src={inputAsset.url} alt="Product" style={{ width: 44, height: 44, objectFit: "cover", borderRadius: 4 }} />
                  <div className="mono" style={{ fontSize: 9.5, color: "var(--ink-60)", flex: 1, wordBreak: "break-all" }}>
                    {inputAsset.hash.slice(0, 16)}…
                    <div style={{ color: "var(--ok)", marginTop: 2 }}>frames will match its palette</div>
                  </div>
                  <button className="dim" style={{ background: "transparent", border: 0, fontSize: 14 }} aria-label="Remove image" onClick={() => setInputAsset(null)}>×</button>
                </div>
              ) : (
                <button className="btn" style={{ justifyContent: "center", fontSize: 10.5 }} onClick={() => fileRef.current?.click()} disabled={uploading}>
                  {uploading ? "Uploading…" : "+ Upload image"}
                </button>
              )}
            </div>
            <div style={{ display: "grid", gap: 6 }}>
              <label htmlFor="brief">Brief</label>
              <textarea id="brief" rows={3} value={brief} onChange={(e) => setBrief(e.target.value)} />
            </div>
            <div style={{ display: "grid", gap: 6 }}>
              <label htmlFor="voicescript">Speech text (optional)</label>
              <textarea
                id="voicescript"
                rows={2}
                value={voiceScript}
                onChange={(e) => setVoiceScript(e.target.value)}
                placeholder="Exact words the voice should speak — empty = auto-written line"
                style={{ resize: "vertical", fontSize: 12 }}
              />
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <div style={{ display: "grid", gap: 6 }}>
                <label htmlFor="voicesel">Voice</label>
                <select id="voicesel" value={voice} onChange={(e) => setVoice(e.target.value)} style={{ fontSize: 12, width: "100%", minWidth: 0 }}>
                  <option value="">Auto</option>
                  <option value="Kore">Female — warm</option>
                  <option value="Leda">Female — bright</option>
                  <option value="Charon">Male — deep</option>
                  <option value="Puck">Male — energetic</option>
                </select>
              </div>
              <div style={{ display: "grid", gap: 6 }}>
                <label htmlFor="musicsel">Music</label>
                <select id="musicsel" value={musicStyle} onChange={(e) => setMusicStyle(e.target.value)} style={{ fontSize: 12, width: "100%", minWidth: 0 }}>
                  <option value="">Lo-fi (default)</option>
                  <option value="cinematic">Cinematic</option>
                  <option value="ambient">Ambient</option>
                  <option value="electronic">Electronic</option>
                  <option value="none">No music</option>
                </select>
              </div>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <div style={{ display: "grid", gap: 6 }}>
                <label htmlFor="shotsel">Shots</label>
                <select id="shotsel" value={nShots} onChange={(e) => setNShots(e.target.value)} style={{ fontSize: 12, width: "100%", minWidth: 0 }}>
                  <option value="2">2 shots</option>
                  <option value="3">3 shots</option>
                  <option value="4">4 shots (all frames)</option>
                </select>
              </div>
              <div style={{ display: "grid", gap: 6 }}>
                <label htmlFor="secsel">Shot length</label>
                <select id="secsel" value={videoSecs} onChange={(e) => setVideoSecs(e.target.value)} style={{ fontSize: 12, width: "100%", minWidth: 0 }}>
                  <option value="">Default</option>
                  <option value="4">4 seconds</option>
                  <option value="6" disabled={!(ents.video_secs || [4]).includes(6)}>6 seconds{!(ents.video_secs || [4]).includes(6) ? " · Standard" : ""}</option>
                  <option value="8" disabled={!(ents.video_secs || [4]).includes(8)}>8 seconds{!(ents.video_secs || [4]).includes(8) ? " · Premium" : ""}</option>
                </select>
              </div>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <div style={{ display: "grid", gap: 6 }}>
                <label htmlFor="branch">Branch</label>
                <input id="branch" value={branch} onChange={(e) => setBranch(e.target.value)} />
              </div>
              <div style={{ display: "grid", gap: 6 }}>
                <label htmlFor="base">Remix from</label>
                <select id="base" value={baseBranch === (branch || "main") ? "" : baseBranch} onChange={(e) => setBaseBranch(e.target.value)}>
                  <option value="">(none)</option>
                  {branches?.filter((b) => b && b !== (branch || "main")).map((b) => (
                    <option key={b} value={b}>{b}</option>
                  ))}
                </select>
              </div>
            </div>
            <button className="btn solid" style={{ justifyContent: "center" }} onClick={runJob} disabled={running || !projectId}>
              {running ? "Pipeline running…" : "Run pipeline →"}
            </button>
            <p className="mono dim" style={{ fontSize: 10.5, lineHeight: 1.5 }}>
              Set “remix from” to an existing branch: unchanged steps are dedup-referenced, only edited prompts regenerate.
            </p>
          </div>

          {/* live event feed */}
          <div>
            <span className="eyebrow">Pipeline feed</span>
            <div className="mono" style={{ marginTop: 10, fontSize: 10.5, display: "grid", gap: 6, maxHeight: 320, overflowY: "auto" }}>
              {events.slice().reverse().map((e, i) => (
                <div key={i} style={{ borderLeft: `2px solid ${e.event.includes("retry") || e.event.includes("error") || e.event.includes("failed") ? "var(--accent)" : e.event === "step.commit" ? "var(--ok)" : "var(--line-strong)"}`, paddingLeft: 8, color: "var(--ink-60)" }}>
                  <b style={{ color: "var(--ink)" }}>{e.event}</b>{" "}
                  {e.step || ""} {e.provider ? `· ${e.provider}` : ""} {e.score != null ? `· ${e.score}/10` : ""}
                  {e.hash ? ` · ${e.hash.slice(0, 8)}` : ""}
                  {e.error && (
                    <div style={{ color: "var(--accent)", marginTop: 3, wordBreak: "break-word", lineHeight: 1.45 }}>
                      {e.error}
                    </div>
                  )}
                  {e.note && (
                    <div style={{ marginTop: 3, wordBreak: "break-word", lineHeight: 1.45 }}>{e.note}</div>
                  )}
                </div>
              ))}
              {!events.length && <span className="dim">Run a pipeline to stream events here.</span>}
            </div>
          </div>
        </aside>

        {/* center: DAG */}
        <main style={{ minWidth: 0, position: "relative" }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodeClick={(_, node) => openCommit(node)}
            fitView
            proOptions={{ hideAttribution: true }}
            minZoom={0.2}
          >
            <Background color="rgba(17,17,16,0.18)" gap={24} size={1} />
            <Controls showInteractive={false} />
            <MiniMap
              pannable
              zoomable
              nodeColor={(n) => n.data?.color || "#111110"}
              nodeStrokeWidth={0}
              maskColor="rgba(233,233,230,0.75)"
              style={{ background: "var(--panel)", border: "1px solid var(--line-strong)", width: 180, height: 120 }}
            />
          </ReactFlow>
          {!nodes.length && (
            <div style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center", pointerEvents: "none" }}>
              <div style={{ textAlign: "center" }}>
                <div className="display" style={{ fontSize: 40, color: "var(--ink-32)" }}>{dagLoading ? "LOADING LEDGER…" : "EMPTY DAG"}</div>
                <p className="mono dim" style={{ fontSize: 12, marginTop: 8 }}>Run a pipeline commits appear here as the graph grows.</p>
              </div>
            </div>
          )}
        </main>

        {/* right: commit inspector */}
        {selected && (
          <aside className="gl-inspector" style={{ width: 380, borderLeft: "1px solid var(--line-strong)", overflowY: "auto", background: "var(--panel)", padding: 18 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span className="eyebrow orange">Commit</span>
              <button className="btn" style={{ padding: "3px 10px", fontSize: 10 }} onClick={() => setSelected(null)}>Close ×</button>
            </div>
            <p className="mono" style={{ fontSize: 11, marginTop: 10, wordBreak: "break-all", color: "var(--ink-60)" }}>{selected.hash}</p>

            {(selected.ext === "mp4" || selected.ext === "webm") && (
              <video controls autoPlay loop playsInline src={selected.url} style={{ width: "100%", marginTop: 12, border: "1px solid var(--line-strong)" }} />
            )}
            {(selected.modality === "image" || selected.ext === "gif") && (
              <img src={selected.url} alt="" style={{ width: "100%", marginTop: 12, border: "1px solid var(--line-strong)" }} />
            )}
            {(selected.modality === "audio" || selected.modality === "voice") && (
              <audio controls src={selected.url} style={{ width: "100%", marginTop: 12 }} />
            )}
            {selected.genblaze?.present && (
              <div className="mono" style={{ marginTop: 10, fontSize: 10, display: "flex", alignItems: "center", gap: 6, color: selected.genblaze.verified ? "var(--ok)" : "var(--accent)" }}>
                <span>{selected.genblaze.verified ? "✓" : "✗"}</span>
                <span>Genblaze manifest {selected.genblaze.verified ? "verified" : "mismatch"} · {(selected.genblaze.canonical_hash || "").slice(0, 12)}</span>
              </div>
            )}
            {selected.url && (
              <a
                className="btn"
                style={{ justifyContent: "center", marginTop: 10, fontSize: 10.5 }}
                href={selected.url}
                download={`${selected.step}-${selected.hash.slice(0, 12)}.${selected.ext}`}
              >
                Download {selected.ext.toUpperCase()} ↓
              </a>
            )}

            <div className="cellgrid" style={{ gridTemplateColumns: "1fr 1fr", marginTop: 14 }}>
              <div className="cell"><div className="v" style={{ fontSize: 14 }}>{selected.branch}</div><div className="k">Branch</div></div>
              <div className="cell"><div className="v" style={{ fontSize: 14 }}>{selected.recipe?.provider}</div><div className="k">Provider</div></div>
              <div className="cell">
                {ents.cost_analytics ? (
                  <>
                    <div className="v" style={{ fontSize: 14 }}>${(selected.cost_usd ?? 0).toFixed(3)}</div>
                    <div className="k">Cost</div>
                  </>
                ) : (
                  <>
                    <div className="v" style={{ fontSize: 12, color: "var(--ink-32)" }} title="Branch cost analytics is a paid feature">🔒</div>
                    <div className="k">Cost · Standard</div>
                  </>
                )}
              </div>
              <div className="cell"><div className="v" style={{ fontSize: 14 }}>{selected.latency_ms}ms</div><div className="k">Latency</div></div>
            </div>

            <div style={{ marginTop: 16 }}>
              <span className="eyebrow">Signature</span>
              <p className="mono" style={{ fontSize: 11.5, marginTop: 8, color: selected.manifest_valid ? "var(--ok)" : "var(--accent)" }}>
                {selected.manifest_valid ? "✓ ed25519 manifest verified" : "✗ manifest missing or invalid"}
              </p>
            </div>

            <div style={{ marginTop: 16 }}>
              <span className="eyebrow">Recipe</span>
              <pre className="mono" style={{ fontSize: 10, marginTop: 8, padding: 10, background: "#fdfdfb", border: "1px solid var(--line)", overflowX: "auto", whiteSpace: "pre-wrap" }}>
                {JSON.stringify(selected.recipe, null, 2)}
              </pre>
            </div>

            <div style={{ marginTop: 16 }}>
              <span className="eyebrow">Eval log — every attempt</span>
              <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
                {(selected.evals || []).map((ev, i) => (
                  <div key={i} className="mono" style={{ fontSize: 10.5, border: "1px solid var(--line)", padding: 8, background: "#fdfdfb" }}>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <b>#{ev.attempt} {ev.provider}</b>
                      <span style={{ color: ev.score >= 7 ? "var(--ok)" : "var(--accent)" }}>
                        {ev.score != null ? `${ev.score}/10` : "error"}
                      </span>
                    </div>
                    <p className="dim" style={{ marginTop: 4, lineHeight: 1.5 }}>{ev.critique}</p>
                  </div>
                ))}
              </div>
            </div>
          </aside>
        )}
      </div>

      {/* ---- delete project confirm ---- */}
      {confirmDelete && (
        <div
          style={{ position: "fixed", inset: 0, zIndex: 80, background: "rgba(17,17,16,0.45)", display: "grid", placeItems: "center", padding: 20 }}
          onClick={() => setConfirmDelete(null)}
        >
          <div
            className="tick"
            style={{ background: "var(--panel)", border: "1px solid var(--accent)", padding: 26, width: 440, maxWidth: "100%" }}
            onClick={(e) => e.stopPropagation()}
          >
            <span className="tag" style={{ borderColor: "var(--accent)", color: "var(--accent)" }}>Delete project</span>
            <h3 className="display" style={{ fontSize: 22, marginTop: 16 }}>DELETE “{confirmDelete.name}”?</h3>
            <p className="mono dim" style={{ fontSize: 11.5, lineHeight: 1.6, marginTop: 12 }}>
              This removes the project, its {confirmDelete.commits} commit record{confirmDelete.commits === 1 ? "" : "s"} and
              its DAG log. Content-addressed assets referenced by other projects are unaffected.
              This can't be undone.
            </p>
            <div style={{ display: "flex", gap: 10, marginTop: 22, justifyContent: "flex-end" }}>
              <button className="btn" onClick={() => setConfirmDelete(null)}>Cancel</button>
              <button className="btn" style={{ background: "var(--accent)", borderColor: "var(--accent)", color: "#fff" }} onClick={deleteProject}>
                Delete permanently
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ---- profile / settings drawer ---- */}
      {panel && (
        <div style={{ position: "fixed", inset: 0, zIndex: 80, display: "flex", justifyContent: "flex-end" }}>
          <div style={{ flex: 1, background: "rgba(17,17,16,0.35)" }} onClick={() => setPanel(null)} />
          <div style={{ width: panel === "works" ? 560 : 420, maxWidth: "100%", background: "var(--panel)", borderLeft: "1px solid var(--line-strong)", overflowY: "auto", padding: 24 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span className="eyebrow orange">
                {panel === "profile" ? "Your profile" : panel === "billing" ? "Billing & plan"
                  : panel === "works" ? "My works" : "Settings"}
              </span>
              <button className="btn" style={{ padding: "3px 10px", fontSize: 10 }} onClick={() => setPanel(null)}>Close ×</button>
            </div>

            {panel === "profile" && (
              <div style={{ marginTop: 22 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
                  <span style={{ width: 52, height: 52, borderRadius: "50%", background: "var(--accent)", color: "#fff", display: "grid", placeItems: "center", fontFamily: "var(--font-mono)", fontSize: 22, fontWeight: 700 }}>
                    {(profileDraft.name || "G").slice(0, 1).toUpperCase()}
                  </span>
                  <div className="mono">
                    <div style={{ fontSize: 14, fontWeight: 700 }}>{profileDraft.name || "guest"}</div>
                    <div className="dim" style={{ fontSize: 11 }}>
                      {user?.via === "google" ? "Signed in with Google" : "Email account"}
                    </div>
                  </div>
                </div>

                <div style={{ display: "grid", gap: 16, marginTop: 24 }}>
                  <div style={{ display: "grid", gap: 6 }}>
                    <label htmlFor="p-name">Display name</label>
                    <input id="p-name" value={profileDraft.name} onChange={(e) => setProfileDraft({ ...profileDraft, name: e.target.value })} />
                  </div>
                  <div style={{ display: "grid", gap: 6 }}>
                    <label htmlFor="p-email">Email</label>
                    <input id="p-email" type="email" value={profileDraft.email} onChange={(e) => setProfileDraft({ ...profileDraft, email: e.target.value })} placeholder="you@studio.dev" />
                  </div>
                  <button className="btn solid" style={{ justifyContent: "center" }} onClick={saveProfile}>Save profile</button>
                </div>

                <div className="cellgrid" style={{ gridTemplateColumns: "1fr 1fr", marginTop: 26 }}>
                  <div className="cell"><div className="v" style={{ fontSize: 16 }}>{projects.length}</div><div className="k">Projects</div></div>
                  <div className="cell"><div className="v" style={{ fontSize: 16 }}>{projects.reduce((n, p) => n + (p.commits || 0), 0)}</div><div className="k">Total commits</div></div>
                </div>
              </div>
            )}

            {panel === "works" && (
              <div style={{ marginTop: 22 }}>
                <p className="mono dim" style={{ fontSize: 11, lineHeight: 1.6 }}>
                  Every pipeline run you've completed, newest first. Deleting a work
                  removes the run and its commits from your ledger.
                </p>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginTop: 18 }}>
                  {works.map((w) => (
                    <article key={w.job_id} style={{ border: "1px solid var(--line-strong)", background: "#fdfdfb", borderRadius: 6, overflow: "hidden" }}>
                      {w.thumb_url ? (w.thumb_url.endsWith(".mp4") || w.thumb_url.endsWith(".webm") ? (
                        <video src={w.thumb_url} muted loop autoPlay playsInline style={{ width: "100%", height: 130, objectFit: "cover", display: "block", background: "#eceae4" }} />
                      ) : (
                        <img src={w.thumb_url} alt="" onError={(e) => { e.currentTarget.src = "/logo.png"; e.currentTarget.style.objectFit = "contain"; e.currentTarget.style.padding = "28px"; }} style={{ width: "100%", height: 130, objectFit: "cover", display: "block", background: "#eceae4" }} />
                      )) : (
                        <div style={{ height: 110, display: "grid", placeItems: "center", padding: 10 }}>
                          <img src="/logo.png" alt="" style={{ width: 34, opacity: 0.5 }} />
                        </div>
                      )}
                      <div style={{ padding: "10px 12px" }}>
                        <div className="mono" style={{ fontSize: 11, fontWeight: 700, display: "flex", justifyContent: "space-between", gap: 6 }}>
                          <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{w.project}</span>
                          <span style={{ color: w.status === "done" ? "var(--ok)" : "var(--accent)" }}>{w.status}</span>
                        </div>
                        <p className="mono dim" style={{ fontSize: 10, marginTop: 4, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={w.brief}>
                          {w.brief}
                        </p>
                        <p className="mono dim" style={{ fontSize: 9.5, marginTop: 4 }}>
                          {w.branch} · {w.commits} commits · {new Date(w.created_at).toLocaleDateString()}
                        </p>
                        <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
                          <button
                            className="btn"
                            style={{ padding: "4px 10px", fontSize: 9.5 }}
                            onClick={() => { setProjectId(w.project_id); setPanel(null); }}
                          >
                            Open
                          </button>
                          {confirmWork === w.job_id ? (
                            <>
                              <button
                                className="btn"
                                style={{ padding: "4px 10px", fontSize: 9.5, background: "var(--accent)", borderColor: "var(--accent)", color: "#fff" }}
                                onClick={() => deleteWork(w.job_id)}
                              >
                                Confirm delete
                              </button>
                              <button
                                className="btn"
                                style={{ padding: "4px 10px", fontSize: 9.5 }}
                                onClick={() => setConfirmWork(null)}
                              >
                                Cancel
                              </button>
                            </>
                          ) : (
                            <button
                              className="btn"
                              style={{ padding: "4px 10px", fontSize: 9.5, color: "var(--accent)", borderColor: "var(--accent)" }}
                              onClick={() => setConfirmWork(w.job_id)}
                            >
                              Delete
                            </button>
                          )}
                        </div>
                      </div>
                    </article>
                  ))}
                </div>
                {!works.length && (
                  <p className="mono dim" style={{ fontSize: 12, marginTop: 20 }}>
                    No works yet run a pipeline and it will appear here.
                  </p>
                )}
              </div>
            )}

            {panel === "billing" && (() => {
              const commitsUsed = projects.reduce((n, p) => n + (p.commits || 0), 0);
              const annual = cycle === "yearly";
              const PLANS = [
                { id: "free", name: "Free", monthly: 0, yearly: 0, limit: 200, blurb: "3 projects · 200 commits/mo" },
                { id: "standard", name: "Standard", monthly: 10, yearly: 105, limit: 2000, blurb: "Unlimited projects · 2,000 commits/mo · cost analytics" },
                { id: "premium", name: "Premium", monthly: 25, yearly: 264, limit: 10000, blurb: "Top tier · 10,000 commits/mo · gate tuning · audit exports" },
              ];
              const order = PLANS.map((p) => p.id);
              const cur = PLANS.find((p) => p.id === plan) || PLANS[0];
              const pct = Math.min(100, Math.round((commitsUsed / cur.limit) * 100));
              const status = user?.subscription_status || "none";
              const renews = user?.current_period_end
                ? new Date(user.current_period_end).toLocaleDateString()
                : null;
              const priceLine = (p) => {
                if (p.monthly === 0) return "$0";
                return annual
                  ? `$${(p.yearly / 12).toFixed(2)}/mo · billed $${p.yearly}/yr`
                  : `$${p.monthly}/mo · billed monthly`;
              };
              return (
                <div style={{ marginTop: 22, display: "grid", gap: 22 }}>
                  {/* subscription status */}
                  {plan !== "free" && (
                    <div style={{ border: `1px solid ${status === "cancelled" ? "var(--accent)" : "var(--ok)"}`, background: "#fdfdfb", padding: 12 }}>
                      <div className="mono" style={{ fontSize: 11, fontWeight: 700, color: status === "cancelled" ? "var(--accent)" : "var(--ok)" }}>
                        {status === "cancelled" ? "Subscription cancelled" : "Subscription active"}
                      </div>
                      <p className="mono dim" style={{ fontSize: 10.5, marginTop: 5, lineHeight: 1.5 }}>
                        {status === "cancelled"
                          ? `You keep ${cur.name} access${renews ? ` until ${renews}` : ""}, then move to Free. No further charges.`
                          : `${renews ? `Renews automatically on ${renews}` : "Active subscription"} · billed ${user?.billing_cycle === "yearly" ? "yearly" : "monthly"}.`}
                      </p>
                      {status !== "cancelled" && (
                        <button
                          className="btn"
                          style={{ padding: "5px 11px", fontSize: 10, marginTop: 10, color: "var(--accent)", borderColor: "var(--accent)" }}
                          onClick={cancelSubscription}
                          disabled={cancelling}
                        >
                          {cancelling ? "Cancelling…" : "Cancel subscription"}
                        </button>
                      )}
                      {status === "cancelled" && (
                        <button
                          className="btn solid"
                          style={{ padding: "5px 11px", fontSize: 10, marginTop: 10 }}
                          onClick={() => changePlan(plan)}
                        >
                          Resubscribe
                        </button>
                      )}
                    </div>
                  )}

                  {/* usage */}
                  <div>
                    <span className="mono dim" style={{ fontSize: 10.5, letterSpacing: "0.08em", textTransform: "uppercase" }}>
                      Usage this cycle — {cur.name} plan
                    </span>
                    <div className="cellgrid" style={{ gridTemplateColumns: "1fr 1fr", marginTop: 10 }}>
                      <div className="cell"><div className="v" style={{ fontSize: 16 }}>{projects.length}</div><div className="k">Projects</div></div>
                      <div className="cell"><div className="v" style={{ fontSize: 16 }}>{commitsUsed} / {cur.limit}</div><div className="k">Commits</div></div>
                    </div>
                    <div style={{ marginTop: 10 }}>
                      <div style={{ height: 6, background: "var(--line)", position: "relative" }}>
                        <div style={{ position: "absolute", inset: "0 auto 0 0", width: `${pct}%`, background: pct > 85 ? "var(--accent)" : "var(--ok)" }} />
                      </div>
                      <p className="mono dim" style={{ fontSize: 10, marginTop: 6 }}>{pct}% of monthly commit allowance</p>
                    </div>
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span className="mono dim" style={{ fontSize: 10.5 }}>Billing cycle:</span>
                    {["monthly", "yearly"].map((cy) => {
                      const active = cycle === cy;
                      return (
                        <button
                          key={cy}
                          className="mono"
                          onClick={() => { setCycle(cy); localStorage.setItem("genlineage.cycle", cy); }}
                          style={{ fontSize: 10, padding: "4px 10px", border: "1px solid var(--line-strong)", background: active ? "var(--ink)" : "transparent", color: active ? "var(--paper)" : "var(--ink-60)", textTransform: "uppercase", letterSpacing: "0.05em" }}
                        >
                          {cy}{cy === "yearly" ? " · 12% off" : ""}
                        </button>
                      );
                    })}
                  </div>

                  {/* plans */}
                  <div style={{ display: "grid", gap: 12 }}>
                    {PLANS.map((p) => {
                      const current = p.id === plan;
                      const up = order.indexOf(p.id) > order.indexOf(plan);
                      return (
                        <div key={p.id} style={{ border: `1px solid ${current ? "var(--accent)" : "var(--line-strong)"}`, background: "#fdfdfb", padding: 14 }}>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 8 }}>
                            <span className="display" style={{ fontSize: 17 }}>{p.name}</span>
                            <span className="mono" style={{ fontSize: 11, fontWeight: 700, textAlign: "right" }}>{priceLine(p)}</span>
                          </div>
                          <p className="mono dim" style={{ fontSize: 10.5, marginTop: 6 }}>{p.blurb}</p>
                          <div style={{ marginTop: 12 }}>
                            {current ? (
                              <span className="tag fill" style={{ fontSize: 9 }}>Current plan</span>
                            ) : (
                              <button className={`btn${up ? " solid" : ""}`} style={{ padding: "6px 12px", fontSize: 10 }} onClick={() => changePlan(p.id)}>
                                {up ? `Upgrade to ${p.name}` : `Downgrade to ${p.name}`}
                              </button>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  <p className="mono dim" style={{ fontSize: 10.5, lineHeight: 1.6, borderTop: "1px solid var(--line)", paddingTop: 14 }}>
                    Payments processed securely by Flutterwave. Paid plans renew
                    automatically each {annual ? "year" : "month"} — cancel any time and
                    keep access until the period ends.
                  </p>
                </div>
              );
            })()}

            {panel === "settings" && (
              <div style={{ marginTop: 22, display: "grid", gap: 22 }}>
                <div style={{ display: "grid", gap: 8 }}>
                  <label htmlFor="s-gate">
                    Quality gate threshold — {settings.gateMin.toFixed(1)}/10
                    {!ents.gate_tuning && <span style={{ color: "var(--accent)" }}> · Premium</span>}
                  </label>
                  <input id="s-gate" type="range" min={5} max={9} step={0.5} value={settings.gateMin}
                    disabled={!ents.gate_tuning}
                    onChange={(e) => saveSettings({ ...settings, gateMin: parseFloat(e.target.value) })}
                    style={{ padding: 0, opacity: ents.gate_tuning ? 1 : 0.4 }} />
                  <p className="mono dim" style={{ fontSize: 10.5, lineHeight: 1.5 }}>
                    {ents.gate_tuning
                      ? "Minimum evaluator score for an output to merge. Higher = stricter, more retries."
                      : "Tuning the merge threshold is a Premium feature — upgrade in Billing to unlock."}
                  </p>
                </div>

                {[
                  ["autoFailover", "Automatic failover", "On gate exhaustion, advance to the backup generation path."],
                  ["liveNotifications", "Live pipeline notifications", "Stream step events into the feed as they happen."],
                ].map(([key, title, desc]) => (
                  <label key={key} style={{ display: "flex", gap: 12, alignItems: "flex-start", cursor: "pointer" }}>
                    <input type="checkbox" checked={settings[key]} onChange={(e) => saveSettings({ ...settings, [key]: e.target.checked })} style={{ width: "auto", marginTop: 3 }} />
                    <span>
                      <span className="mono" style={{ fontSize: 12.5, fontWeight: 700 }}>{title}</span>
                      <p className="mono dim" style={{ fontSize: 10.5, lineHeight: 1.5, marginTop: 3, textTransform: "none", letterSpacing: 0 }}>{desc}</p>
                    </span>
                  </label>
                ))}

                <div style={{ borderTop: "1px solid var(--line)", paddingTop: 18 }}>
                  <span className="mono dim" style={{ fontSize: 10.5 }}>Settings save automatically to this browser.</span>
                </div>
                <div style={{ borderTop: "1px solid var(--line)", paddingTop: 14 }}>
                  <button className="btn" style={{ justifyContent: "center", width: "100%", color: "var(--accent)", borderColor: "var(--accent)" }}
                    onClick={() => setShowDelete(true)}>
                    Delete account permanently
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ---- saved toast ---- */}
      {savedFlash && (
        <div className="mono" style={{ position: "fixed", bottom: 24, left: "50%", transform: "translateX(-50%)", zIndex: 90, background: "var(--ink)", color: "var(--paper)", padding: "10px 20px", fontSize: 12, borderRadius: 2 }}>
          ✓ {savedFlash}
        </div>
      )}
    </div>
  );
}
