/**
 * src/lib/notion.ts
 * ─────────────────────────────────────────────────────────────────────────────
 * Singleton Notion client + helpers dla baz `Klienci` i `Zadania`.
 * Używaj WYŁĄCZNIE tych funkcji – nigdy nie importuj @notionhq/client bezpośrednio
 * w komponentach ani Server Actions.
 */

import { Client, isFullPage } from "@notionhq/client";
import type {
  CreatePageParameters,
  QueryDatabaseParameters,
  UpdatePageParameters,
} from "@notionhq/client/build/src/api-endpoints";
import type {
  NotionKlient,
  NotionZadanie,
  ZadanieStatus,
  ZadanieTyp,
} from "./notion-types";

// ─── Singleton ────────────────────────────────────────────────────────────────

let _notion: Client | null = null;

export function getNotionClient(): Client {
  if (!_notion) {
    const token = process.env.NOTION_TOKEN;
    if (!token) throw new Error("NOTION_TOKEN is not set in environment");
    _notion = new Client({ auth: token });
  }
  return _notion;
}

// ─── DB IDs ───────────────────────────────────────────────────────────────────

function getKlienciDbId(): string {
  const id = process.env.NOTION_DB_KLIENCI;
  if (!id) throw new Error("NOTION_DB_KLIENCI is not set");
  return id;
}

function getZadaniaDbId(): string {
  const id = process.env.NOTION_DB_ZADANIA;
  if (!id) throw new Error("NOTION_DB_ZADANIA is not set");
  return id;
}

// ─── Helper: raw page → NotionKlient ─────────────────────────────────────────

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function pageToKlient(page: any): NotionKlient {
  const p = page.properties;
  return {
    notionId: page.id,
    imieNazwisko: p["Imię i nazwisko"]?.title?.[0]?.plain_text ?? "",
    email: p["Email"]?.email ?? "",
    telefon: p["Telefon"]?.phone_number ?? null,
    firma: p["Firma"]?.rich_text?.[0]?.plain_text ?? null,
    createdAt: page.created_time,
    panelUserId: p["Panel User ID"]?.rich_text?.[0]?.plain_text ?? null,
    aktywny: p["Aktywny"]?.checkbox ?? true,
  };
}

// ─── Helper: raw page → NotionZadanie ────────────────────────────────────────

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function pageToZadanie(page: any): NotionZadanie {
  const p = page.properties;
  return {
    notionId: page.id,
    tytul: p["Tytuł"]?.title?.[0]?.plain_text ?? "",
    status: p["Status"]?.status?.name as ZadanieStatus,
    typ: p["Typ"]?.select?.name as ZadanieTyp,
    klientId: p["Klient"]?.relation?.[0]?.id ?? null,
    driveFolderUrl: p["Drive Folder URL"]?.url ?? null,
    opis: p["Opis"]?.rich_text?.[0]?.plain_text ?? null,
    deadline: p["Deadline"]?.date?.start ?? null,
    logCzasuMin: p["Log Czasu (min)"]?.number ?? 0,
    checklist: p["Checklist"]?.rich_text?.[0]?.plain_text
      ? JSON.parse(p["Checklist"].rich_text[0].plain_text)
      : [],
    createdAt: page.created_time,
    updatedAt: page.last_edited_time,
  };
}

// ═══════════════════════════════════════════════════════════════════════════════
// KLIENCI
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Pobierz klienta po adresie email (unikalne pole).
 */
export async function getKlientByEmail(
  email: string
): Promise<NotionKlient | null> {
  const notion = getNotionClient();
  const res = await notion.databases.query({
    database_id: getKlienciDbId(),
    filter: { property: "Email", email: { equals: email } },
    page_size: 1,
  });
  const page = res.results[0];
  if (!page || !isFullPage(page)) return null;
  return pageToKlient(page);
}

/**
 * Pobierz klienta po Panel User ID (Prisma/NextAuth ID).
 */
export async function getKlientByPanelUserId(
  panelUserId: string
): Promise<NotionKlient | null> {
  const notion = getNotionClient();
  const res = await notion.databases.query({
    database_id: getKlienciDbId(),
    filter: {
      property: "Panel User ID",
      rich_text: { equals: panelUserId },
    },
    page_size: 1,
  });
  const page = res.results[0];
  if (!page || !isFullPage(page)) return null;
  return pageToKlient(page);
}

/**
 * Utwórz nowego klienta w bazie Notion.
 */
export async function createKlient(data: {
  imieNazwisko: string;
  email: string;
  telefon?: string;
  firma?: string;
  panelUserId: string;
}): Promise<NotionKlient> {
  const notion = getNotionClient();

  const params: CreatePageParameters = {
    parent: { database_id: getKlienciDbId() },
    properties: {
      "Imię i nazwisko": {
        title: [{ text: { content: data.imieNazwisko } }],
      },
      Email: { email: data.email },
      ...(data.telefon && { Telefon: { phone_number: data.telefon } }),
      ...(data.firma && {
        Firma: { rich_text: [{ text: { content: data.firma } }] },
      }),
      "Panel User ID": {
        rich_text: [{ text: { content: data.panelUserId } }],
      },
      Aktywny: { checkbox: true },
    },
  };

  const page = await notion.pages.create(params);
  if (!isFullPage(page)) throw new Error("Notion: created page is not full");
  return pageToKlient(page);
}

// ═══════════════════════════════════════════════════════════════════════════════
// ZADANIA
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Pobierz wszystkie zadania klienta (po jego Notion page ID).
 */
export async function getZadaniaForKlient(
  klientNotionId: string
): Promise<NotionZadanie[]> {
  const notion = getNotionClient();
  const res = await notion.databases.query({
    database_id: getZadaniaDbId(),
    filter: {
      property: "Klient",
      relation: { contains: klientNotionId },
    },
    sorts: [{ timestamp: "created_time", direction: "descending" }],
  });
  return res.results.filter(isFullPage).map(pageToZadanie);
}

/**
 * Pobierz zadania według statusu (np. "W montażu" dla Adobe API).
 */
export async function getZadaniaByStatus(
  status: ZadanieStatus,
  klientNotionId?: string
): Promise<NotionZadanie[]> {
  const notion = getNotionClient();

  const filter: QueryDatabaseParameters["filter"] = klientNotionId
    ? {
        and: [
          { property: "Status", status: { equals: status } },
          { property: "Klient", relation: { contains: klientNotionId } },
        ],
      }
    : { property: "Status", status: { equals: status } };

  const res = await notion.databases.query({
    database_id: getZadaniaDbId(),
    filter,
    sorts: [{ property: "Deadline", direction: "ascending" }],
  });

  return res.results.filter(isFullPage).map(pageToZadanie);
}

/**
 * Pobierz pojedyncze zadanie po ID.
 */
export async function getZadanieById(id: string): Promise<NotionZadanie | null> {
  const notion = getNotionClient();
  try {
    const page = await notion.pages.retrieve({ page_id: id });
    if (!isFullPage(page)) return null;
    return pageToZadanie(page);
  } catch {
    return null;
  }
}

/**
 * Utwórz nowe zadanie w bazie Notion.
 * Wywoływany przez Server Action po złożeniu projektu przez klienta.
 */
export async function createZadanie(data: {
  tytul: string;
  typ: ZadanieTyp;
  klientNotionId: string;
  opis?: string;
  deadline?: string; // ISO date string
  driveFolderUrl?: string;
}): Promise<NotionZadanie> {
  const notion = getNotionClient();

  const params: CreatePageParameters = {
    parent: { database_id: getZadaniaDbId() },
    properties: {
      Tytuł: { title: [{ text: { content: data.tytul } }] },
      Status: { status: { name: "Nowe" } },
      Typ: { select: { name: data.typ } },
      Klient: { relation: [{ id: data.klientNotionId }] },
      ...(data.opis && {
        Opis: { rich_text: [{ text: { content: data.opis } }] },
      }),
      ...(data.deadline && {
        Deadline: { date: { start: data.deadline } },
      }),
      ...(data.driveFolderUrl && {
        "Drive Folder URL": { url: data.driveFolderUrl },
      }),
      "Log Czasu (min)": { number: 0 },
      Checklist: {
        rich_text: [{ text: { content: JSON.stringify([]) } }],
      },
    },
  };

  const page = await notion.pages.create(params);
  if (!isFullPage(page)) throw new Error("Notion: created page is not full");
  return pageToZadanie(page);
}

/**
 * Zaktualizuj status zadania.
 */
export async function updateZadanieStatus(
  zadanieId: string,
  status: ZadanieStatus
): Promise<void> {
  const notion = getNotionClient();
  const params: UpdatePageParameters = {
    page_id: zadanieId,
    properties: { Status: { status: { name: status } } },
  };
  await notion.pages.update(params);
}

/**
 * Zaktualizuj link do folderu Drive w zadaniu.
 */
export async function updateZadanieDriveUrl(
  zadanieId: string,
  url: string
): Promise<void> {
  const notion = getNotionClient();
  await notion.pages.update({
    page_id: zadanieId,
    properties: { "Drive Folder URL": { url } },
  });
}

/**
 * Zapisz checklistę (format JSON) do pola rich_text "Checklist".
 */
export async function updateZadanieChecklist(
  zadanieId: string,
  checklist: Array<{ id: string; label: string; done: boolean }>
): Promise<void> {
  const notion = getNotionClient();
  await notion.pages.update({
    page_id: zadanieId,
    properties: {
      Checklist: {
        rich_text: [{ text: { content: JSON.stringify(checklist) } }],
      },
    },
  });
}

/**
 * Dodaj wpis czasu (Time Tracking) – inkrementuje pole "Log Czasu (min)".
 */
export async function addTimeLog(
  zadanieId: string,
  minuty: number
): Promise<{ totalMin: number }> {
  const notion = getNotionClient();
  const zadanie = await getZadanieById(zadanieId);
  if (!zadanie) throw new Error(`Zadanie ${zadanieId} not found`);

  const totalMin = (zadanie.logCzasuMin ?? 0) + minuty;
  await notion.pages.update({
    page_id: zadanieId,
    properties: { "Log Czasu (min)": { number: totalMin } },
  });
  return { totalMin };
}
