// The "desk" function: the website's subscribe form, its confirm / change-topics / unsubscribe
// links, and the claim checker. Everything a visitor sends is checked here; the keys stay here.
//
// POST JSON {action, ...}:
//   subscribe {email, topics, website}   website is a hidden field: people leave it empty, bots fill it
//   confirm {token, topics}   me {token}   topics {token, topics}   unsubscribe {token}
//   check {text, paper}   get {id}
// POST ?unsub=TOKEN   Gmail's one-click unsubscribe        GET ?unsub=TOKEN   sends people to the website

import type { Env, Fetch } from "./ai.ts";
import { arxivId, counts, fetchPaper, finalVerdicts, findClaims, judgeClaims } from "./checker.ts";
import { DB } from "./db.ts";
import { confirmEmail, type Mailer } from "./mail.ts";

export type Settings = {
  site_url: string;
  from_name: string;
  allowed_origins: string[];
  topics: { slug: string; label: string }[];
  models: Record<string, string>;
  checker: { checks_per_day?: number; checks_per_visitor?: number; subscribes_per_visitor?: number; max_claims?: number };
};

export type Deps = { env: Env; fetcher: Fetch; mailer: Mailer; settings: Settings; now?: () => Date };

class Problem extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

const TOKEN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

async function sha256(text: string): Promise<string> {
  const bytes = new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text)));
  return [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function shortId(): string {
  const abc = "abcdefghijkmnpqrstuvwxyz23456789"; // no look-alikes (l, 1, o, 0)
  return [...crypto.getRandomValues(new Uint8Array(10))].map((b) => abc[b % abc.length]).join("");
}

function maskEmail(email: string): string {
  const [name, domain] = email.split("@");
  return `${name.slice(0, 1)}${"*".repeat(Math.max(2, Math.min(5, name.length - 1)))}@${domain}`;
}

export function makeHandler(deps: Deps) {
  const { env, fetcher, mailer, settings } = deps;
  const now = deps.now || (() => new Date());
  const limits = { checks_per_day: 120, checks_per_visitor: 8, subscribes_per_visitor: 5, max_claims: 6, ...settings.checker };
  const slugs = new Set(settings.topics.map((t) => t.slug));
  const labelsFor = (chosen: string[]) =>
    settings.topics.filter((t) => !chosen.length || chosen.includes(t.slug)).map((t) => t.label);
  const cleanTopics = (x: unknown): string[] => {
    const list = Array.isArray(x) ? x : typeof x === "string" ? x.split(",") : [];
    const picked = [...new Set(list.map((s) => String(s).trim()).filter((s) => slugs.has(s)))];
    return picked.length === slugs.size ? [] : picked; // every topic is stored as "all"
  };
  const db = () => {
    const key = env.get("DESK_DB_KEY"), url = env.get("SUPABASE_URL");
    if (!key || !url) throw new Problem(503, "The desk isn't fully set up yet. Please try again later.");
    return new DB(url, key, fetcher);
  };
  const site = settings.site_url.replace(/\/?$/, "/");

  function cors(origin: string | null): Record<string, string> {
    const allowed = origin && settings.allowed_origins.includes(origin) ? origin : settings.allowed_origins[0];
    return {
      "access-control-allow-origin": allowed,
      "access-control-allow-methods": "POST, GET, OPTIONS",
      "access-control-allow-headers": "content-type, apikey, authorization, x-client-info",
      "vary": "Origin",
    };
  }

  async function visitorId(req: Request): Promise<string> {
    const ip = (req.headers.get("x-forwarded-for") || "").split(",")[0].trim() ||
      req.headers.get("cf-connecting-ip") || req.headers.get("x-real-ip") || "unknown";
    return (await sha256(`${ip}|${env.get("DESK_DB_KEY") || "desk"}`)).slice(0, 24); // never the IP itself
  }

  async function underLimit(d: DB, kind: string, visitor: string, perVisitor: number, perDay?: number) {
    const since = new Date(now().getTime() - 24 * 3600 * 1000).toISOString();
    const mine = await d.count(`usage_log?kind=eq.${kind}&visitor=eq.${visitor}&created_at=gte.${since}&select=id`);
    if (mine >= perVisitor) throw new Problem(429, "That's the daily limit from here. Please come back tomorrow.");
    if (perDay !== undefined) {
      const all = await d.count(`usage_log?kind=eq.${kind}&created_at=gte.${since}&select=id`);
      if (all >= perDay) throw new Problem(429, "The checker has hit its free daily limit. Please come back tomorrow.");
    }
    await d.insert("usage_log", { kind, visitor });
  }

  // ------------------------------------------------------------------ subscribers

  async function subscribe(body: Record<string, unknown>, req: Request) {
    if (String(body.website || "").trim()) return { ok: true }; // a bot filled the hidden field; say yes and do nothing
    const email = String(body.email || "").trim().toLowerCase();
    if (email.length > 254 || !EMAIL.test(email)) throw new Problem(400, "That email address doesn't look right.");
    const topics = cleanTopics(body.topics);
    const d = db();
    await underLimit(d, "subscribe", await visitorId(req), limits.subscribes_per_visitor);

    const found = await d.select<{ token: string; confirm_sent_at: string | null }>(
      `subscribers?email=eq.${encodeURIComponent(email)}&select=token,confirm_sent_at`);
    let token: string;
    if (found.length) {
      token = found[0].token;
      const last = found[0].confirm_sent_at ? new Date(found[0].confirm_sent_at).getTime() : 0;
      if (now().getTime() - last < 10 * 60 * 1000) return { ok: true }; // sent a few minutes ago already
    } else {
      token = (await d.insert<{ token: string }>("subscribers", { email, topics })).token;
    }
    const link = `${site}?confirm=${token}${topics.length ? `&t=${topics.join(",")}` : ""}`;
    const mail = confirmEmail(link, labelsFor(topics), site);
    try {
      await mailer(email, mail.subject, mail.html, mail.text);
    } catch (e) {
      console.error("confirm email failed:", e instanceof Error ? e.message : e);
      throw new Problem(502, "The confirmation email couldn't be sent just now. Please try again in a few minutes.");
    }
    await d.update(`subscribers?token=eq.${token}`, { confirm_sent_at: now().toISOString() });
    return { ok: true }; // the same answer whether or not the address was already on the list
  }

  function tokenOf(body: Record<string, unknown>): string {
    const token = String(body.token || "").trim();
    if (!TOKEN.test(token)) throw new Problem(400, "This link is broken. Try the link in your latest email.");
    return token;
  }

  async function confirm(body: Record<string, unknown>) {
    const token = tokenOf(body);
    const patch: Record<string, unknown> = { confirmed: true, confirmed_at: now().toISOString() };
    if (body.topics !== undefined && body.topics !== null && body.topics !== "") patch.topics = cleanTopics(body.topics);
    const rows = await db().update<{ email: string; topics: string[] }>(`subscribers?token=eq.${token}`, patch);
    if (!rows.length) throw new Problem(404, "This link has expired. Sign up again and a new one will come.");
    return { ok: true, email: maskEmail(rows[0].email), topics: rows[0].topics, labels: labelsFor(rows[0].topics) };
  }

  async function me(body: Record<string, unknown>) {
    const rows = await db().select<{ email: string; topics: string[]; confirmed: boolean }>(
      `subscribers?token=eq.${tokenOf(body)}&select=email,topics,confirmed`);
    if (!rows.length) throw new Problem(404, "This address is no longer on the list.");
    return { ok: true, email: maskEmail(rows[0].email), topics: rows[0].topics, confirmed: rows[0].confirmed, labels: labelsFor(rows[0].topics) };
  }

  async function setTopics(body: Record<string, unknown>) {
    const topics = cleanTopics(body.topics);
    const rows = await db().update<{ topics: string[] }>(`subscribers?token=eq.${tokenOf(body)}`, { topics });
    if (!rows.length) throw new Problem(404, "This address is no longer on the list.");
    return { ok: true, topics: rows[0].topics, labels: labelsFor(rows[0].topics) };
  }

  async function unsubscribe(token: string) {
    await db().remove(`subscribers?token=eq.${token}`);
    return { ok: true }; // also fine if it was already gone
  }

  // ------------------------------------------------------------------ claim checker

  async function check(body: Record<string, unknown>, req: Request) {
    const text = String(body.text || "").replace(/\r/g, "").trim();
    if (text.length < 15) throw new Problem(400, "Paste the post or claim you want to check (a sentence or more).");
    if (text.length > 3000) throw new Problem(400, "That's a bit long. Paste up to 3,000 characters.");
    const id = arxivId(String(body.paper || "")) || arxivId(text);
    if (!id) throw new Problem(400, "Add the paper's arXiv link, like arxiv.org/abs/2511.01234.");

    const d = db();
    const cacheKey = await sha256(`${id}\n${text.toLowerCase().replace(/\s+/g, " ")}`);
    const cached = await d.select<{ id: string; result: Record<string, unknown> }>(
      `claim_checks?cache_key=eq.${cacheKey}&select=id,result`);
    if (cached.length) return { ok: true, id: cached[0].id, ...cached[0].result };

    await underLimit(d, "check", await visitorId(req), limits.checks_per_visitor, limits.checks_per_day);
    const paper = await fetchPaper(id, fetcher).catch(() => {
      throw new Problem(502, "arXiv didn't answer just now. Please try again in a minute.");
    });
    if (!paper) throw new Problem(404, `There's no arXiv paper with the id ${id}.`);

    const models = settings.models;
    const found = await findClaims(text, paper, limits.max_claims, models, env, fetcher).catch(() => {
      throw new Problem(503, "The AI is busy right now. Please try again in a minute.");
    });
    const result: Record<string, unknown> = {
      paper: { id: paper.id, title: paper.title, url: paper.url, authors: paper.authors.slice(0, 6), more_authors: Math.max(0, paper.authors.length - 6) },
      text,
      created_at: now().toISOString(),
    };
    if (!found.value.length) {
      return { ok: true, id: null, ...result, claims: [], counts: counts([]), note: "No factual claim about the paper was found in that text." };
    }
    const judged = await judgeClaims(found.value, paper, models, env, fetcher).catch(() => {
      throw new Problem(503, "The checker is busy right now. Please try again in a minute.");
    });
    const claims = finalVerdicts(found.value, judged.value, paper.abstract);
    Object.assign(result, { claims, counts: counts(claims), checked_by: { claims: found.by, verdicts: judged.by } });

    const shareId = shortId();
    await d.insert("claim_checks", { id: shareId, cache_key: cacheKey, paper_id: paper.id, paper_title: paper.title, input_text: text, result });
    return { ok: true, id: shareId, ...result };
  }

  async function getCheck(body: Record<string, unknown>) {
    const id = String(body.id || "").trim();
    if (!/^[a-z0-9]{6,16}$/.test(id)) throw new Problem(400, "That share link is broken.");
    const rows = await db().select<{ id: string; result: Record<string, unknown> }>(`claim_checks?id=eq.${id}&select=id,result`);
    if (!rows.length) throw new Problem(404, "This check doesn't exist (or was removed).");
    return { ok: true, id: rows[0].id, ...rows[0].result };
  }

  // ------------------------------------------------------------------ routing

  return async function handle(req: Request): Promise<Response> {
    const origin = req.headers.get("origin");
    const headers = cors(origin);
    const json = (status: number, data: unknown) =>
      new Response(JSON.stringify(data), { status, headers: { ...headers, "content-type": "application/json" } });
    if (req.method === "OPTIONS") return new Response(null, { status: 204, headers });

    const url = new URL(req.url);
    const unsub = url.searchParams.get("unsub");
    try {
      if (unsub !== null) {
        if (req.method === "GET") return Response.redirect(`${site}?unsub=${encodeURIComponent(unsub)}`, 303);
        if (!TOKEN.test(unsub)) throw new Problem(400, "This link is broken.");
        await unsubscribe(unsub); // Gmail's one-click button
        return new Response("You are unsubscribed from The Scholar's Desk.", { status: 200, headers });
      }
      if (req.method !== "POST") throw new Problem(405, "Use POST.");
      if (origin && !settings.allowed_origins.includes(origin)) throw new Problem(403, "This website can't use the desk.");
      const body = await req.json().catch(() => null);
      if (!body || typeof body !== "object") throw new Problem(400, "Send JSON.");
      switch (body.action) {
        case "subscribe": return json(200, await subscribe(body, req));
        case "confirm": return json(200, await confirm(body));
        case "me": return json(200, await me(body));
        case "topics": return json(200, await setTopics(body));
        case "unsubscribe": return json(200, await unsubscribe(tokenOf(body)));
        case "check": return json(200, await check(body, req));
        case "get": return json(200, await getCheck(body));
        default: throw new Problem(400, "Unknown action.");
      }
    } catch (e) {
      if (e instanceof Problem) return json(e.status, { ok: false, error: e.message });
      console.error("desk error:", e instanceof Error ? e.message : e);
      return json(500, { ok: false, error: "Something went wrong on our side. Please try again." });
    }
  };
}
