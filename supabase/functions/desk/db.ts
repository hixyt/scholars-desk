// A small client for Supabase's REST API, used with the secret key (DESK_DB_KEY).

import type { Fetch } from "./ai.ts";

export class DB {
  constructor(private url: string, private key: string, private fetcher: Fetch) {}

  private headers(extra: Record<string, string> = {}): Record<string, string> {
    const h: Record<string, string> = { apikey: this.key, "content-type": "application/json", ...extra };
    if (this.key.split(".").length === 3) h.authorization = `Bearer ${this.key}`; // old-style JWT keys
    return h;
  }

  private async call(method: string, path: string, body?: unknown, extra: Record<string, string> = {}) {
    const r = await this.fetcher(`${this.url.replace(/\/$/, "")}/rest/v1/${path}`, {
      method,
      headers: this.headers(extra),
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(15000),
    });
    if (!r.ok) throw new Error(`database ${method} ${path.split("?")[0]} answered ${r.status}: ${(await r.text()).slice(0, 200)}`);
    return r;
  }

  async select<T>(path: string): Promise<T[]> {
    return await (await this.call("GET", path)).json();
  }

  async insert<T>(table: string, row: unknown): Promise<T> {
    const rows = await (await this.call("POST", table, row, { prefer: "return=representation" })).json();
    return rows[0];
  }

  async update<T>(path: string, patch: unknown): Promise<T[]> {
    return await (await this.call("PATCH", path, patch, { prefer: "return=representation" })).json();
  }

  async remove<T>(path: string): Promise<T[]> {
    return await (await this.call("DELETE", path, undefined, { prefer: "return=representation" })).json();
  }

  async count(path: string): Promise<number> {
    const r = await this.call("HEAD", path, undefined, { prefer: "count=exact" });
    const total = (r.headers.get("content-range") || "").split("/")[1];
    return Number(total) || 0;
  }
}
