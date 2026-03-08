/**
 * src/app/api/adobe/tasks/[id]/checklist/route.ts
 * ─────────────────────────────────────────────────────────────────────────────
 * PATCH /api/adobe/tasks/:id/checklist
 *
 * Wtyczka Adobe Premiere przesyła zaktualizowaną checklistę (np. po odhaczeniu
 * etapu montażu). Dane zapisywane jako JSON w polu rich_text "Checklist" w Notion.
 *
 * Body:
 * {
 *   "checklist": [
 *     { "id": "uuid", "label": "Rough cut", "done": true },
 *     { "id": "uuid", "label": "Color grade", "done": false }
 *   ]
 * }
 */

import { NextRequest, NextResponse } from "next/server";
import { updateZadanieChecklist, getZadanieById } from "@/lib/notion";
import { AdobeChecklistUpdateSchema, safeParse } from "@/lib/validations";

function verifyAdobeToken(req: NextRequest): boolean {
  const secret = process.env.ADOBE_API_SECRET;
  if (!secret) return false;
  return req.headers.get("authorization") === `Bearer ${secret}`;
}

export async function PATCH(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  if (!verifyAdobeToken(req)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id } = params;

  // Sprawdź czy zadanie istnieje
  const zadanie = await getZadanieById(id);
  if (!zadanie) {
    return NextResponse.json(
      { error: "Not Found", message: `Zadanie ${id} nie istnieje.` },
      { status: 404 }
    );
  }

  // Parsuj i waliduj body
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json(
      { error: "Bad Request", message: "Nieprawidłowy JSON." },
      { status: 400 }
    );
  }

  const parsed = safeParse(AdobeChecklistUpdateSchema, body);
  if (!parsed.success) {
    return NextResponse.json(
      { error: "Validation Error", message: parsed.error },
      { status: 422 }
    );
  }

  try {
    await updateZadanieChecklist(id, parsed.data.checklist);
    return NextResponse.json({
      ok: true,
      zadanieId: id,
      checklist: parsed.data.checklist,
      updatedAt: new Date().toISOString(),
    });
  } catch (err) {
    console.error("[PATCH /api/adobe/tasks/[id]/checklist]", err);
    return NextResponse.json(
      { error: "Internal Server Error", message: "Nie udało się zapisać checklisty." },
      { status: 500 }
    );
  }
}
