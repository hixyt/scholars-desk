// Tests for the desk function with a pretend database, Gemini, Groq and arXiv.
// Run: deno test supabase/tests/desk_test.ts

function assert(ok: unknown, message = "assertion failed"): asserts ok {
  if (!ok) throw new Error(message);
}
function assertEquals(actual: unknown, expected: unknown, message = "") {
  const a = JSON.stringify(actual), e = JSON.stringify(expected);
  if (a !== e) throw new Error(`${message ? message + ": " : ""}expected ${e}, got ${a}`);
}
import { makeHandler, type Settings } from "../functions/desk/app.ts";
import settingsJson from "../functions/desk/settings.json" with { type: "json" };

const settings = settingsJson as Settings;
const SITE = "https://hixyt.github.io";
const ABSTRACT =
  "We study how large language model agents help office workers with spreadsheet tasks. In a study with 40 participants, " +
  "agents reduced task time by 31 percent compared to working alone. However, participants trusted wrong answers in some cases, " +
  "which suggests that people need clear signals about when an agent may be wrong.";

type Row = Record<string, unknown>;

function fakeWorld(judge: (claims: { claim_id: string; text: string }[]) => unknown[]) {
  const tables: Record<string, Row[]> = { subscribers: [], usage_log: [], claim_checks: [] };
  const calls = { gemini: 0, groq: 0, arxiv: 0, mail: [] as { to: string; subject: string; text: string }[] };
  let ids = 1;

  function match(row: Row, query: URLSearchParams) {
    for (const [k, v] of query) {
      if (k === "select" || k === "order") continue;
      const [op, ...rest] = v.split(".");
      const want = decodeURIComponent(rest.join("."));
      if (op === "eq" && String(row[k]) !== want) return false;
      if (op === "gte" && String(row[k]) < want) return false;
    }
    return true;
  }

  const fetcher = async (input: string | URL | Request, init: RequestInit = {}): Promise<Response> => {
    const url = new URL(String(input));
    const method = (init.method || "GET").toUpperCase();
    if (url.hostname.endsWith("supabase.co")) {
      const table = url.pathname.split("/").pop()!;
      const rows = tables[table];
      const q = url.searchParams;
      if (method === "HEAD") {
        const n = rows.filter((r) => match(r, q)).length;
        return new Response(null, { status: 200, headers: { "content-range": `*/${n}` } });
      }
      if (method === "GET") return Response.json(rows.filter((r) => match(r, q)));
      if (method === "POST") {
        const row: Row = { id: ids++, created_at: new Date().toISOString(), ...JSON.parse(String(init.body)) };
        if (table === "subscribers") {
          if (rows.some((r) => r.email === row.email)) return new Response("duplicate", { status: 409 });
          Object.assign(row, { token: crypto.randomUUID(), confirmed: false, confirm_sent_at: null });
        }
        rows.push(row);
        return Response.json([row], { status: 201 });
      }
      if (method === "PATCH") {
        const hit = rows.filter((r) => match(r, q));
        hit.forEach((r) => Object.assign(r, JSON.parse(String(init.body))));
        return Response.json(hit);
      }
      if (method === "DELETE") {
        const hit = rows.filter((r) => match(r, q));
        tables[table] = rows.filter((r) => !hit.includes(r));
        return Response.json(hit);
      }
    }
    if (url.hostname === "export.arxiv.org") {
      calls.arxiv++;
      if (url.searchParams.get("id_list") === "2611.99999") return new Response("<feed></feed>");
      return new Response(`<feed><entry><id>http://arxiv.org/abs/2611.12345v1</id><title>Agents at the
        Spreadsheet</title><summary>${ABSTRACT}</summary><author><name>Asha Rao</name></author><author><name>Ben Ito</name></author></entry></feed>`);
    }
    if (url.hostname === "generativelanguage.googleapis.com") {
      calls.gemini++;
      const claims = ["Agents cut spreadsheet task time by 31 percent.", "The paper proves agents never make mistakes.",
        "It was tested with 500 people.", "Agents make office workers twice as fast.", "The agents run on a quantum computer."];
      return Response.json({ candidates: [{ content: { parts: [{ text: JSON.stringify({ claims }) }] } }] });
    }
    if (url.hostname === "api.groq.com") {
      calls.groq++;
      const prompt = JSON.parse(String(init.body)).messages[1].content as string;
      const items = JSON.parse(prompt.slice(prompt.indexOf("[")));
      return Response.json({ choices: [{ message: { content: JSON.stringify({ results: judge(items) }) } }] });
    }
    throw new Error(`unexpected fetch ${url}`);
  };
  const env = new Map(Object.entries({
    DESK_DB_KEY: "sb_secret_test", SUPABASE_URL: "https://moflbxuaozrcsqbzrwwt.supabase.co",
    GEMINI_API_KEY: "g", GROQ_API_KEY: "q",
  }));
  const handle = makeHandler({
    env: { get: (k: string) => env.get(k) }, fetcher: fetcher as typeof fetch, settings,
    mailer: async (to, subject, _html, text) => { calls.mail.push({ to, subject, text }); },
  });
  const post = (body: unknown, ip = "1.2.3.4", origin = SITE) =>
    handle(new Request("https://moflbxuaozrcsqbzrwwt.supabase.co/functions/v1/desk", {
      method: "POST", headers: { origin, "content-type": "application/json", "x-forwarded-for": ip }, body: JSON.stringify(body),
    }));
  return { tables, calls, handle, post };
}

const goodJudge = (items: { claim_id: string }[]) => items.map((c) => ({
  c1: { claim_id: "c1", evidence: "agents reduced task time by 31 percent compared to working alone", reason: "The abstract says this.", verdict: "supported" },
  c2: { claim_id: "c2", evidence: "agents are flawless and never make any mistake", reason: "Made-up quote.", verdict: "supported" },
  c3: { claim_id: "c3", evidence: "In a study with 40 participants", reason: "It says participants.", verdict: "supported" },
  c4: { claim_id: "c4", evidence: "agents reduced task time by 31 percent compared to working alone", reason: "31 percent is not twice as fast.", verdict: "overstated" },
  c5: { claim_id: "c5", evidence: "", reason: "Not mentioned.", verdict: "not_in_abstract" },
} as Record<string, unknown>)[c.claim_id]);

Deno.test("subscribe sends one confirmation, and a hidden-field bot gets nothing", async () => {
  const w = fakeWorld(goodJudge);
  let r = await w.post({ action: "subscribe", email: "  Reader@Example.com ", topics: ["health", "trust", "nope"] });
  assertEquals(r.status, 200);
  assertEquals(w.tables.subscribers.length, 1);
  assertEquals(w.tables.subscribers[0].email, "reader@example.com");
  assertEquals(w.tables.subscribers[0].topics, ["health", "trust"]);
  assertEquals(w.calls.mail.length, 1);
  assert(w.calls.mail[0].text.includes("?confirm="));
  assert(w.calls.mail[0].text.includes("&t=health,trust"));
  assert(w.calls.mail[0].text.includes("AI in health"));

  r = await w.post({ action: "subscribe", email: "reader@example.com", topics: ["health"] });
  assertEquals(r.status, 200);
  assertEquals(w.calls.mail.length, 1, "no second email within 10 minutes");

  r = await w.post({ action: "subscribe", email: "bot@example.com", website: "http://spam" });
  assertEquals((await r.json()).ok, true);
  assertEquals(w.tables.subscribers.length, 1);

  r = await w.post({ action: "subscribe", email: "not-an-email" });
  assertEquals(r.status, 400);
});

Deno.test("all topics are stored as 'all', and the confirm link carries no topic list", async () => {
  const w = fakeWorld(goodJudge);
  await w.post({ action: "subscribe", email: "all@example.com", topics: settings.topics.map((t) => t.slug) });
  assertEquals(w.tables.subscribers[0].topics, []);
  assert(!w.calls.mail[0].text.includes("&t="));
});

Deno.test("confirm, read, change topics and unsubscribe with the token", async () => {
  const w = fakeWorld(goodJudge);
  await w.post({ action: "subscribe", email: "reader@example.com", topics: ["health"] });
  const token = String(w.tables.subscribers[0].token);

  let data = await (await w.post({ action: "confirm", token, topics: "education,business" })).json();
  assertEquals(data.ok, true);
  assertEquals(data.email, "r*****@example.com");
  assertEquals(data.labels, ["AI in education", "Business and money"]);
  assertEquals(w.tables.subscribers[0].confirmed, true);

  data = await (await w.post({ action: "me", token })).json();
  assertEquals(data.topics, ["education", "business"]);

  data = await (await w.post({ action: "topics", token, topics: ["trust"] })).json();
  assertEquals(data.labels, ["Trust and safety"]);

  assertEquals((await w.post({ action: "confirm", token: "not-a-token" })).status, 400);
  data = await (await w.post({ action: "unsubscribe", token })).json();
  assertEquals(data.ok, true);
  assertEquals(w.tables.subscribers.length, 0);
  assertEquals((await w.post({ action: "me", token })).status, 404);
});

Deno.test("Gmail's one-click unsubscribe works, and a plain click goes to the website", async () => {
  const w = fakeWorld(goodJudge);
  await w.post({ action: "subscribe", email: "reader@example.com" });
  const token = String(w.tables.subscribers[0].token);
  const base = "https://moflbxuaozrcsqbzrwwt.supabase.co/functions/v1/desk?unsub=" + token;
  const r1 = await w.handle(new Request(base));
  assertEquals(r1.status, 303);
  assertEquals(r1.headers.get("location"), `https://hixyt.github.io/scholars-desk/?unsub=${token}`);
  assertEquals(w.tables.subscribers.length, 1);
  const r2 = await w.handle(new Request(base, { method: "POST", body: "List-Unsubscribe=One-Click" }));
  assertEquals(r2.status, 200);
  assertEquals(w.tables.subscribers.length, 0);
});

Deno.test("the checker keeps real proof and refuses fake proof", async () => {
  const w = fakeWorld(goodJudge);
  const text = "Huge! This paper proves AI agents never make mistakes and make office workers twice as fast. arxiv.org/abs/2611.12345v2";
  const r = await w.post({ action: "check", text });
  assertEquals(r.status, 200);
  const data = await r.json();
  assertEquals(data.paper.title, "Agents at the Spreadsheet");
  assertEquals(data.paper.authors, ["Asha Rao", "Ben Ito"]);
  const verdicts = data.claims.map((c: { verdict: string }) => c.verdict);
  assertEquals(verdicts, ["supported", "not_in_abstract", "overstated", "overstated", "not_in_abstract"]);
  assertEquals(data.claims[1].evidence, "", "a fake quote is never shown");
  assert(data.claims[2].reason.includes("500"), "the made-up number is named");
  assertEquals(data.counts, { supported: 1, overstated: 2, contradicted: 0, not_in_abstract: 2 });
  assert(/^[a-z0-9]{10}$/.test(data.id));
  assertEquals(w.tables.claim_checks.length, 1);

  const again = await (await w.post({ action: "check", text, paper: "" })).json();
  assertEquals(again.id, data.id);
  assertEquals(w.calls.gemini, 1, "the same post is answered from the saved check");
  assertEquals(w.calls.groq, 1);

  const shared = await (await w.post({ action: "get", id: data.id }, "9.9.9.9")).json();
  assertEquals(shared.claims.length, 5);
  assertEquals(shared.text, text);
});

Deno.test("checker input errors are plain and helpful", async () => {
  const w = fakeWorld(goodJudge);
  let data = await (await w.post({ action: "check", text: "short" })).json();
  assert(data.error.includes("Paste"));
  data = await (await w.post({ action: "check", text: "This paper says agents are great at everything." })).json();
  assert(data.error.includes("arXiv link"));
  const r = await w.post({ action: "check", text: "This paper says agents are great at everything.", paper: "https://arxiv.org/abs/2611.99999" });
  assertEquals(r.status, 404);
});

Deno.test("daily limits per visitor, and only known websites", async () => {
  const w = fakeWorld(goodJudge);
  for (let i = 0; i < 8; i++) {
    const r = await w.post({ action: "check", text: `Claim number ${i}: agents cut task time by 31 percent.`, paper: "2611.12345" });
    assertEquals(r.status, 200);
  }
  const r = await w.post({ action: "check", text: "One more: agents cut task time by 31 percent.", paper: "2611.12345" });
  assertEquals(r.status, 429);
  const other = await w.post({ action: "check", text: "From elsewhere: agents cut task time by 31 percent.", paper: "2611.12345" }, "5.6.7.8");
  assertEquals(other.status, 200, "another visitor still has checks left");
  assert(!w.tables.usage_log.some((u) => String(u.visitor).includes("1.2.3.4")), "no IP is stored");

  assertEquals((await w.post({ action: "get", id: "abcdefghij" }, "1.1.1.1", "https://evil.example")).status, 403);
  const pre = await w.handle(new Request("https://x.supabase.co/functions/v1/desk", { method: "OPTIONS", headers: { origin: SITE } }));
  assertEquals(pre.status, 204);
  assertEquals(pre.headers.get("access-control-allow-origin"), SITE);
});
