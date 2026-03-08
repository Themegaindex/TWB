/**
 * src/lib/notion-types.ts
 * ─────────────────────────────────────────────────────────────────────────────
 * Typy TypeScript odzwierciedlające schemat baz Notion.
 * Zmieniaj TYLKO tutaj, nigdy nie hardkoduj nazw pól w kodzie aplikacji.
 */

// ─── Statusy i typy (muszą być identyczne z opcjami w Notion) ────────────────

export type ZadanieStatus =
  | "Nowe"
  | "W trakcie"
  | "W montażu"
  | "Oczekuje na materiały"
  | "Gotowe do akceptacji"
  | "Zaakceptowane"
  | "Archiwum";

export type ZadanieTyp = "Montaż" | "Nagranie" | "Fotografia" | "Grafika" | "Inne";

// ─── Klienci ──────────────────────────────────────────────────────────────────

/**
 * Odpowiednik rekordu z bazy Notion `Klienci`.
 * Panel User ID = ID użytkownika w Prisma/NextAuth (klucz synchronizacji).
 */
export interface NotionKlient {
  /** Notion page ID (UUID) */
  notionId: string;
  imieNazwisko: string;
  email: string;
  telefon: string | null;
  firma: string | null;
  /** ID z tabeli User w Prisma (klucz FK synchronizacji) */
  panelUserId: string | null;
  aktywny: boolean;
  createdAt: string;
}

// ─── Zadania ──────────────────────────────────────────────────────────────────

export interface ChecklistItem {
  id: string;
  label: string;
  done: boolean;
}

/**
 * Odpowiednik rekordu z bazy Notion `Zadania`.
 */
export interface NotionZadanie {
  /** Notion page ID (UUID) */
  notionId: string;
  tytul: string;
  status: ZadanieStatus;
  typ: ZadanieTyp;
  /** Notion page ID powiązanego klienta (relacja) */
  klientId: string | null;
  driveFolderUrl: string | null;
  opis: string | null;
  deadline: string | null; // ISO date
  logCzasuMin: number;
  checklist: ChecklistItem[];
  createdAt: string;
  updatedAt: string;
}

// ─── Schematy baz danych (dokumentacja dla admina) ────────────────────────────

/**
 * SCHEMAT BAZY `Klienci`
 * ┌─────────────────────────┬──────────────┬─────────────────────────────────┐
 * │ Nazwa Property          │ Typ Notion   │ Uwagi                           │
 * ├─────────────────────────┼──────────────┼─────────────────────────────────┤
 * │ Imię i nazwisko         │ Title        │ Pole tytułowe (wymagane)        │
 * │ Email                   │ Email        │ Unikalny – klucz wyszukiwania   │
 * │ Telefon                 │ Phone        │ Opcjonalne                      │
 * │ Firma                   │ Rich Text    │ Opcjonalne                      │
 * │ Panel User ID           │ Rich Text    │ FK → Prisma User.id             │
 * │ Aktywny                 │ Checkbox     │ Soft-delete                     │
 * └─────────────────────────┴──────────────┴─────────────────────────────────┘
 *
 * SCHEMAT BAZY `Zadania`
 * ┌─────────────────────────┬──────────────┬─────────────────────────────────┐
 * │ Tytuł                   │ Title        │ Pole tytułowe                   │
 * │ Status                  │ Status       │ Wbudowany typ (pipeline view)   │
 * │ Typ                     │ Select       │ Montaż / Nagranie / …           │
 * │ Klient                  │ Relation     │ → baza Klienci                  │
 * │ Drive Folder URL        │ URL          │ Link do folderu w Drive/NC      │
 * │ Opis                    │ Rich Text    │ Briefing od klienta             │
 * │ Deadline                │ Date         │ Termin realizacji               │
 * │ Log Czasu (min)         │ Number       │ Suma minut (Adobe Time Track)   │
 * │ Checklist               │ Rich Text    │ JSON: ChecklistItem[]           │
 * └─────────────────────────┴──────────────┴─────────────────────────────────┘
 */
export const NOTION_SCHEMA_DOCS = null; // marker – plik czysto deklaratywny
