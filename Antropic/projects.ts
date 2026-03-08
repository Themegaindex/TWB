/**
 * src/actions/projects.ts
 * ─────────────────────────────────────────────────────────────────────────────
 * Server Actions związane z projektami klienta.
 * "use server" zapewnia, że kod nigdy nie trafia do bundla clienta.
 */

"use server";

import { revalidatePath } from "next/cache";
import { auth } from "@/lib/auth"; // NextAuth / Prisma session helper
import {
  getKlientByPanelUserId,
  createZadanie,
  updateZadanieDriveUrl,
} from "@/lib/notion";
import { createProjectFolder } from "@/lib/drive";
import { CreateProjectSchema, safeParse } from "@/lib/validations";
import type { CreateProjectInput } from "@/lib/validations";

// ─── Typy odpowiedzi ──────────────────────────────────────────────────────────

export type ActionResult<T = undefined> =
  | { success: true; data: T }
  | { success: false; error: string };

// ─── createProject ────────────────────────────────────────────────────────────

/**
 * Server Action: Klient składa nowy projekt.
 *
 * Przepływ:
 *  1. Walidacja wejścia (Zod)
 *  2. Sprawdzenie sesji
 *  3. Pobranie rekordu Notion dla zalogowanego klienta
 *  4. Utworzenie zadania w Notion (status = "Nowe")
 *  5. Utworzenie folderu na chmurze (Drive / Nextcloud)
 *  6. Zapis URL folderu z powrotem do Notion
 *  7. Revalidacja cache
 *
 * @param rawData - niezwalidowane dane z FormData lub obiektu
 */
export async function createProject(
  rawData: CreateProjectInput
): Promise<ActionResult<{ zadanieId: string; driveFolderUrl: string }>> {
  // 1. Walidacja
  const parsed = safeParse(CreateProjectSchema, rawData);
  if (!parsed.success) {
    return { success: false, error: parsed.error };
  }
  const { tytul, typ, opis, deadline } = parsed.data;

  // 2. Sesja
  const session = await auth();
  if (!session?.user?.id) {
    return { success: false, error: "Nie jesteś zalogowany." };
  }

  // 3. Klient w Notion
  const klient = await getKlientByPanelUserId(session.user.id);
  if (!klient) {
    return {
      success: false,
      error:
        "Nie znaleziono Twojego profilu w systemie. Skontaktuj się z supportem.",
    };
  }

  // 4. Utwórz zadanie w Notion
  let zadanie;
  try {
    zadanie = await createZadanie({
      tytul,
      typ,
      klientNotionId: klient.notionId,
      opis,
      deadline,
    });
  } catch (err) {
    console.error("[createProject] Notion error:", err);
    return {
      success: false,
      error: "Nie udało się utworzyć projektu w systemie. Spróbuj ponownie.",
    };
  }

  // 5. Utwórz folder na chmurze
  let folder;
  try {
    folder = await createProjectFolder(klient.imieNazwisko, tytul);
  } catch (err) {
    console.error("[createProject] Cloud folder error:", err);
    // Projekt istnieje w Notion, ale folder się nie udał – nie blokujemy
    // klienta, logujemy błąd do obsłużenia przez admina
    return {
      success: true,
      data: {
        zadanieId: zadanie.notionId,
        driveFolderUrl: "",
      },
    };
  }

  // 6. Zapisz URL do Notion
  try {
    await updateZadanieDriveUrl(zadanie.notionId, folder.url);
  } catch (err) {
    console.error("[createProject] Notion Drive URL update error:", err);
    // Non-fatal – projekt i folder istnieją
  }

  // 7. Revalidacja
  revalidatePath("/dashboard/projekty");

  return {
    success: true,
    data: {
      zadanieId: zadanie.notionId,
      driveFolderUrl: folder.url,
    },
  };
}

// ─── getUserProjects ──────────────────────────────────────────────────────────

import { getZadaniaForKlient } from "@/lib/notion";
import type { NotionZadanie } from "@/lib/notion-types";

/**
 * Pobiera listę projektów zalogowanego klienta.
 * Używaj w Server Components (bez "use client").
 */
export async function getUserProjects(): Promise<
  ActionResult<NotionZadanie[]>
> {
  const session = await auth();
  if (!session?.user?.id) {
    return { success: false, error: "Nie jesteś zalogowany." };
  }

  const klient = await getKlientByPanelUserId(session.user.id);
  if (!klient) {
    return { success: false, error: "Profil klienta nie znaleziony." };
  }

  try {
    const zadania = await getZadaniaForKlient(klient.notionId);
    return { success: true, data: zadania };
  } catch (err) {
    console.error("[getUserProjects]", err);
    return {
      success: false,
      error: "Nie udało się pobrać projektów. Spróbuj ponownie.",
    };
  }
}
