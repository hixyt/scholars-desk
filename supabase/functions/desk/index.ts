// Entry point Supabase runs. The logic lives in app.ts so it can be tested without Supabase.

import { makeHandler, type Settings } from "./app.ts";
import { gmailMailer } from "./mail.ts";
import settings from "./settings.json" with { type: "json" };

const s = settings as Settings;
Deno.serve(makeHandler({ env: Deno.env, fetcher: fetch, mailer: gmailMailer(Deno.env, s.from_name), settings: s }));
