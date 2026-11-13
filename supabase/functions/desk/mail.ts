// The confirmation email for new subscribers, sent through Gmail (port 465; Supabase blocks 25 and 587).

import type { Env } from "./ai.ts";

export type Mailer = (to: string, subject: string, html: string, text: string) => Promise<void>;

export function gmailMailer(env: Env, fromName: string): Mailer {
  return async (to, subject, html, text) => {
    const user = (env.get("GMAIL_ADDRESS") || "").trim();
    const pass = (env.get("GMAIL_APP_PASSWORD") || "").replace(/\s+/g, ""); // Google shows it in groups of four
    if (!user || !pass) throw new Error("the Gmail address or app password is missing");
    const { default: nodemailer } = await import("npm:nodemailer@6.9.16");
    const transport = nodemailer.createTransport({ host: "smtp.gmail.com", port: 465, secure: true, auth: { user, pass } });
    await transport.sendMail({ from: { name: fromName, address: user }, to, subject, html, text });
  };
}

const esc = (s: string) => s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]!));

export function confirmEmail(link: string, labels: string[], siteUrl: string): { subject: string; html: string; text: string } {
  const topics = labels.join(" · ");
  const subject = "Confirm your seat at The Scholar's Desk";
  const text = [
    "Someone (hopefully you) asked for The Scholar's Desk, a free email with new AI papers every morning at 6:17 AM India time.",
    "",
    `Topics: ${topics}`,
    "",
    `Confirm here: ${link}`,
    "",
    "If this wasn't you, ignore this email and nothing will be sent.",
    siteUrl,
  ].join("\n");
  const html = `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#0B0907;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#0B0907;"><tr><td align="center" style="padding:36px 14px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:520px;background:#EFE6D0;border-radius:4px;">
<tr><td height="6" style="height:6px;line-height:6px;font-size:6px;background:#5E1C17;border-radius:4px 4px 0 0;">&nbsp;</td></tr>
<tr><td style="padding:30px 30px 8px;font-family:Cinzel,Georgia,serif;font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#A3342A;">The Scholar&rsquo;s Desk</td></tr>
<tr><td style="padding:0 30px;font-family:'Playfair Display',Georgia,serif;font-size:27px;line-height:1.3;font-style:italic;color:#2B2118;">One click and your seat is saved.</td></tr>
<tr><td style="padding:16px 30px 0;font-family:Georgia,serif;font-size:16px;line-height:1.65;color:#2B2118;">
Someone (hopefully you) asked for The Scholar&rsquo;s Desk: new AI papers in plain words every morning at 6:17&nbsp;AM India time, each line checked against the paper, each with a weekend project.</td></tr>
<tr><td style="padding:16px 30px 0;font-family:Georgia,serif;font-size:14px;line-height:1.6;color:#6B5A45;"><b style="color:#2B2118;">Your topics:</b> ${esc(topics)}</td></tr>
<tr><td style="padding:26px 30px 8px;"><a href="${esc(link)}" style="display:inline-block;padding:13px 20px;background:#2B2118;border-radius:3px;font-family:Cinzel,Georgia,serif;font-size:12px;letter-spacing:2px;text-transform:uppercase;color:#EFE6D0;text-decoration:none;">Yes, send it to me</a></td></tr>
<tr><td style="padding:14px 30px 30px;font-family:Georgia,serif;font-size:13px;line-height:1.6;font-style:italic;color:#6B5A45;">If this wasn&rsquo;t you, ignore this email and nothing will be sent.</td></tr>
</table>
<p style="margin:18px 0 0;font-family:Georgia,serif;font-size:12px;color:#A3957E;"><a href="${esc(siteUrl)}" style="color:#CFAE6B;">${esc(siteUrl.replace(/^https?:\/\//, ""))}</a></p>
</td></tr></table></body></html>`;
  return { subject, html, text };
}
