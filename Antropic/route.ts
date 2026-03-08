/**
 * src/app/api/adobe/tasks/route.ts
 * ─────────────────────────────────────────────────────────────────────────────
 * GET  /api/adobe/tasks          → lista zadań ze statusem "W montażu"
 *
 * Autoryzacja: Bearer token (zmienna ADOBE_API_SECRET w .env).
 * Wtyczka Adobe Premiere powinna wysyłać nagłówek:
 *   Authorization: Bearer <ADOBE_API_SECRET>
 *
 * Opcjonalne query params:
 *   ?klientId=<notion_page_id>   → filtruj po kliencie
 *   ?status=W montażu            → nadpisz domyślny status (dla testów)
 */

import { NextRequest, NextResponse } from "next/server";
import { getZadaniaByStatus } from "@/lib/notion";
import type { ZadanieStatus } from "@/lib/notion-types";

// ─── Auth middleware helper ───────────────────────────────────────────────────

function verifyAdobeToken(req: NextRequest): boolean {
  const secret = process.env.ADOBE_API_SECRET;
  if (!secret) {
    console.error("ADOBE_API_SECRET not configured");
    return false;
  }
  const auth = req.headers.get("authorization") ?? "";
  return auth === `Bearer ${secret}`;
}

// ─── GET ──────────────────────────────────────────────────────────────────────

export async function GET(req: NextRequest) {
  // Auth
  if (!verifyAdobeToken(req)) {
    return NextResponse.json(
      { error: "Unauthorized", message: "Invalid or missing Bearer token." },
      { status: 401 }
    );
  }

  const { searchParams } = req.nextUrl;
  const klientId = searchParams.get("klientId") ?? undefined;

  // Domyślny status dla Adobe = "W montażu"
  const rawStatus = searchParams.get("status") ?? "W montażu";
  const allowedStatuses: ZadanieStatus[] = [
    "Nowe",
    "W trakcie",
    "W montażu",
    "Oczekuje na materiały",
    "Gotowe do akceptacji",
    "Zaakceptowane",
    "Archiwum",
  ];

  if (!allowedStatuses.includes(rawStatus as ZadanieStatus)) {
    return NextResponse.json(
      { error: "Bad Request", message: `Nieprawidłowy status: ${rawStatus}` },
      { status: 400 }
    );
  }

  const status = rawStatus as ZadanieStatus;

  try {
    const zadania = await getZadaniaByStatus(status, klientId);

    // Mapowanie do lekkiego DTO dla wtyczki Adobe
    const payload = zadania.map((z) => ({
      id: z.notionId,
      tytul: z.tytul,
      status: z.status,
      typ: z.typ,
      klientId: z.klientId,
      driveFolderUrl: z.driveFolderUrl,
      deadline: z.deadline,
      logCzasuMin: z.logCzasuMin,
      checklist: z.checklist,
      createdAt: z.createdAt,
      updatedAt: z.updatedAt,
    }));

    return NextResponse.json(
      {
        ok: true,
        count: payload.length,
        zadania: payload,
        fetchedAt: new Date().toISOString(),
      },
      {
        status: 200,
        headers: {
          // Krótkie cache dla wtyczki (30s)
          "Cache-Control": "private, max-age=30",
        },
      }
    );
  } catch (err) {
    console.error("[GET /api/adobe/tasks]", err);
    return NextResponse.json(
      {
        error: "Internal Server Error",
        message: "Nie udało się pobrać zadań z Notion.",
      },
      { status: 500 }
    );
  }
}
