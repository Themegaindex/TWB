/**
 * src/app/api/admin/zadania/[id]/status/route.ts
 * ─────────────────────────────────────────────────────────────────────────────
 * PATCH /api/admin/zadania/:id/status
 * Autoryzacja: sesja NextAuth z rolą "admin".
 */

import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { updateZadanieStatus } from "@/lib/notion";
import { UpdateZadanieStatusSchema, safeParse } from "@/lib/validations";

export async function PATCH(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  const session = await auth();

  // Sprawdź rolę admina – dodaj pole `role` do Prisma schema i NextAuth session
  if (!session?.user || (session.user as { role?: string }).role !== "admin") {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Bad Request" }, { status: 400 });
  }

  const parsed = safeParse(UpdateZadanieStatusSchema, {
    zadanieId: params.id,
    ...(body as object),
  });

  if (!parsed.success) {
    return NextResponse.json(
      { error: "Validation Error", message: parsed.error },
      { status: 422 }
    );
  }

  try {
    await updateZadanieStatus(parsed.data.zadanieId, parsed.data.status);
    return NextResponse.json({
      ok: true,
      zadanieId: parsed.data.zadanieId,
      status: parsed.data.status,
      updatedAt: new Date().toISOString(),
    });
  } catch (err) {
    console.error("[PATCH admin/zadania/status]", err);
    return NextResponse.json(
      { error: "Internal Server Error" },
      { status: 500 }
    );
  }
}
