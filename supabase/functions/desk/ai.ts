// Calls to Gemini and Groq. The keys come from Supabase secrets and never reach the browser.

export type Env = { get(name: string): string | undefined };
export type Fetch = typeof fetch;

export class AIError extends Error {}

function parseJSON(text: string): unknown {
  let t = (text || "").trim();
  if (t.startsWith("```")) t = t.replace(/^```(?:json)?/, "").replace(/```$/, "").trim();
  return JSON.parse(t);
}

export async function gemini(
  model: string, system: string, prompt: string, env: Env, fetcher: Fetch, timeoutMs = 40000,
): Promise<unknown> {
  const key = env.get("GEMINI_API_KEY");
  if (!key) throw new AIError("no Gemini key");
  const r = await fetcher(`https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`, {
    method: "POST",
    headers: { "content-type": "application/json", "x-goog-api-key": key },
    body: JSON.stringify({
      systemInstruction: { parts: [{ text: system }] },
      contents: [{ role: "user", parts: [{ text: prompt }] }],
      generationConfig: { responseMimeType: "application/json", temperature: 0.2 },
    }),
    signal: AbortSignal.timeout(timeoutMs),
  });
  if (!r.ok) throw new AIError(`Gemini ${model} answered ${r.status}`);
  const data = await r.json();
  const text = (data?.candidates?.[0]?.content?.parts || []).map((p: { text?: string }) => p.text || "").join("");
  if (!text) throw new AIError(`Gemini ${model} sent an empty reply`);
  return parseJSON(text);
}

export async function groq(
  model: string, system: string, prompt: string, env: Env, fetcher: Fetch,
  schema?: Record<string, unknown>, timeoutMs = 60000,
): Promise<unknown> {
  const key = env.get("GROQ_API_KEY");
  if (!key) throw new AIError("no Groq key");
  const body: Record<string, unknown> = {
    model,
    messages: [{ role: "system", content: system }, { role: "user", content: prompt }],
    temperature: 0.3,
    max_completion_tokens: 3000, // counts the model's hidden thinking too
    response_format: schema
      ? { type: "json_schema", json_schema: { name: "reply", strict: true, schema } }
      : { type: "json_object" },
  };
  if (model.startsWith("openai/gpt-oss")) body.reasoning_effort = "low";
  const r = await fetcher("https://api.groq.com/openai/v1/chat/completions", {
    method: "POST",
    headers: { "content-type": "application/json", authorization: `Bearer ${key}` },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(timeoutMs),
  });
  if (!r.ok) throw new AIError(`Groq ${model} answered ${r.status}`);
  const data = await r.json();
  const text = data?.choices?.[0]?.message?.content;
  if (!text) throw new AIError(`Groq ${model} sent an empty reply`);
  return parseJSON(text);
}

// Try each (name, call) in order and return the first answer that passes `accept`.
export async function firstThatWorks<T>(
  tries: [string, () => Promise<unknown>][], accept: (x: unknown) => T | null,
): Promise<{ value: T; by: string }> {
  const errors: string[] = [];
  for (const [name, call] of tries) {
    try {
      const value = accept(await call());
      if (value !== null) return { value, by: name };
      errors.push(`${name}: reply in the wrong shape`);
    } catch (e) {
      errors.push(`${name}: ${e instanceof Error ? e.message : String(e)}`);
    }
  }
  throw new AIError(errors.join("; "));
}
