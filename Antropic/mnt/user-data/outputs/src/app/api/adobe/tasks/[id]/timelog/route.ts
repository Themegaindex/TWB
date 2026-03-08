/**
 * src/app/api/adobe/tasks/[id]/timelog/route.ts
 * ─────────────────────────────────────────────────────────────────────────────
 * POST /api/adobe/tasks/:id/timelog
 *
 * Wtyczka Adobe Premiere Pro raportuje przepracowany czas po skończeniu sesji.
 * Endpoint inkrementuje pole "Log Czasu (min)" w Notion.
 *
 * Body:
 * {
 *   "minuty": 45,
 *   "notatka": "Rough cut sekwencja otwierająca"  // opcjonalne
 * }
 *
 * Response:
 * {
 *   "ok": true,
 *   "zadanieId": "...",
 *   "minutyDodane": 45,
 *   "totalMin": 120,
 *   "totalFormatted": "2h 0min"
 * }
 */

import { NextRequest, NextResponse } from "next/server";
import { addTimeLog, getZadanieById } from "@/lib/notion";
import { AdobeTimelogSchema, safeParse } from "@/lib/validations";

function verifyAdobeToken(req: NextRequest): boolean {
  const secret = process.env.ADOBE_API_SECRET;
  if (!secret) return false;
  return req.headers.get("authorization") === `Bearer ${secret}`;
}

function formatMinutes(total: number): string {
  const h = Math.floor(total / 60);
  const m = total % 60;
  if (h === 0) return `${m}min`;
  return `${h}h ${m}min`;
}

export async function POST(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  if (!verifyAdobeToken(req)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id } = params;

  // Sprawdź zadanie
  const zadanie = await getZadanieById(id);
  if (!zadanie) {
    return NextResponse.json(
      { error: "Not Found", message: `Zadanie ${id} nie istnieje.` },
      { status: 404 }
    );
  }

  // Parsuj body
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json(
      { error: "Bad Request", message: "Nieprawidłowy JSON." },
      { status: 400 }
    );
  }

  const parsed = safeParse(AdobeTimelogSchema, body);
  if (!parsed.success) {
    return NextResponse.json(
      { error: "Validation Error", message: parsed.error },
      { status: 422 }
    );
  }

  const { minuty, notatka } = parsed.data;

  try {
    const { totalMin } = await addTimeLog(id, minuty);

    // Opcjonalnie: zapisz notatkę jako komentarz do strony Notion
    if (notatka) {
      // Można rozszerzyć o notion.comments.create(...)
      console.info(`[timelog] ${id} +${minuty}min: "${notatka}"`);
    }

    return NextResponse.json({
      ok: true,
      zadanieId: id,
      minutyDodane: minuty,
      totalMin,
      totalFormatted: formatMinutes(totalMin),
      loggedAt: new Date().toISOString(),
    });
  } catch (err) {
    console.error("[POST /api/adobe/tasks/[id]/timelog]", err);
    return NextResponse.json(
      {
        error: "Internal Server Error",
        message: "Nie udało się zapisać czasu pracy.",
      },
      { status: 500 }
    );
  }
}

// ─── GET – podgląd logów czasu ────────────────────────────────────────────────

export async function GET(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  if (!verifyAdobeToken(req)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const zadanie = await getZadanieById(params.id);
  if (!zadanie) {
    return NextResponse.json({ error: "Not Found" }, { status: 404 });
  }

  return NextResponse.json({
    ok: true,
    zadanieId: params.id,
    totalMin: zadanie.logCzasuMin,
    totalFormatted: formatMinutes(zadanie.logCzasuMin),
  });
}
