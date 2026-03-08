/**
 * src/actions/auth.ts
 * ─────────────────────────────────────────────────────────────────────────────
 * Server Actions: rejestracja klienta.
 * Przy rejestracji tworzymy zarówno użytkownika w Prisma jak i wpis w Notion.
 */

"use server";

import bcrypt from "bcryptjs";
import { prisma } from "@/lib/prisma"; // Twój singleton Prisma Client
import { createKlient, getKlientByEmail } from "@/lib/notion";
import { RegisterSchema, safeParse } from "@/lib/validations";
import type { RegisterInput } from "@/lib/validations";
import type { ActionResult } from "./projects";

// ─── registerClient ───────────────────────────────────────────────────────────

/**
 * Rejestracja nowego klienta.
 *
 * Przepływ:
 *  1. Walidacja (Zod)
 *  2. Sprawdzenie duplikatu emaila w Prisma
 *  3. Hash hasła
 *  4. Zapis w Prisma (DB lokalna)
 *  5. Sprawdzenie czy wpis w Notion już istnieje (idempotentność)
 *  6. Tworzenie wpisu w Notion z Panel User ID
 */
export async function registerClient(
  rawData: RegisterInput
): Promise<ActionResult<{ userId: string }>> {
  // 1. Walidacja
  const parsed = safeParse(RegisterSchema, rawData);
  if (!parsed.success) {
    return { success: false, error: parsed.error };
  }
  const { imieNazwisko, email, password, telefon, firma } = parsed.data;

  // 2. Duplikat emaila (Prisma)
  const existing = await prisma.user.findUnique({ where: { email } });
  if (existing) {
    return {
      success: false,
      error: "Konto z tym adresem email już istnieje.",
    };
  }

  // 3. Hash hasła
  const hashedPassword = await bcrypt.hash(password, 12);

  // 4. Zapis w Prisma
  const user = await prisma.user.create({
    data: {
      name: imieNazwisko,
      email,
      password: hashedPassword,
    },
  });

  // 5. Sprawdź Notion (idempotentność przy retry)
  const notionExisting = await getKlientByEmail(email);

  // 6. Tworzenie w Notion
  if (!notionExisting) {
    try {
      await createKlient({
        imieNazwisko,
        email,
        ...(telefon && { telefon }),
        ...(firma && { firma }),
        panelUserId: user.id,
      });
    } catch (err) {
      // Nie rollbackujemy Prisma – admin może ręcznie dodać lub cron naprawi
      console.error("[registerClient] Notion sync failed:", err);
      // Zwracamy sukces bo konto JEST stworzone – Notion można naprawić
    }
  } else {
    // Aktualizuj Panel User ID jeśli brakuje (np. po imporcie ręcznym)
    // (tu można wywołać updateKlientPanelUserId gdy taka funkcja istnieje)
  }

  return { success: true, data: { userId: user.id } };
}
