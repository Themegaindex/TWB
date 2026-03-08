# Freelancer Web Panel — Architektura i Setup

## Struktura plików (nowych)

```
src/
├── lib/
│   ├── notion.ts          ✅ Singleton klienta + wszystkie CRUD helpery
│   ├── notion-types.ts    ✅ Typy TS + dokumentacja schematu baz
│   ├── validations.ts     ✅ Zod schematy (auth, projekt, adobe, admin)
│   └── drive.ts           ✅ Google Drive + Nextcloud WebDAV abstrakcja
│
├── actions/
│   ├── projects.ts        ✅ createProject, getUserProjects (Server Actions)
│   └── auth.ts            ✅ registerClient (Prisma + Notion sync)
│
├── components/
│   └── FileUploadZone.tsx ✅ Drag & Drop upload (react-dropzone + shadcn/ui)
│
└── app/
    └── api/
        ├── upload/
        │   └── route.ts   ✅ POST /api/upload (Google Drive / Nextcloud)
        ├── adobe/
        │   └── tasks/
        │       ├── route.ts                      ✅ GET  /api/adobe/tasks
        │       └── [id]/
        │           ├── checklist/route.ts         ✅ PATCH /api/adobe/tasks/:id/checklist
        │           └── timelog/route.ts           ✅ POST  /api/adobe/tasks/:id/timelog
        └── admin/
            └── zadania/[id]/
                └── status/route.ts               ✅ PATCH /api/admin/zadania/:id/status
```

---

## Schemat Notion (Database of Truth)

### Baza `Klienci`

| Nazwa Property    | Typ Notion  | Uwagi                                         |
|-------------------|-------------|-----------------------------------------------|
| Imię i nazwisko   | **Title**   | Pole tytułowe (wymagane)                      |
| Email             | Email       | Unikalny — klucz wyszukiwania                 |
| Telefon           | Phone       | Opcjonalne                                    |
| Firma             | Rich Text   | Opcjonalne                                    |
| Panel User ID     | Rich Text   | FK → Prisma `User.id` (klucz synchronizacji) |
| Aktywny           | Checkbox    | Soft-delete (default: true)                   |

### Baza `Zadania`

| Nazwa Property     | Typ Notion   | Uwagi                                          |
|--------------------|--------------|------------------------------------------------|
| Tytuł              | **Title**    | Pole tytułowe                                  |
| Status             | Status       | Wbudowany typ — pipeline/kanban view           |
| Typ                | Select       | Montaż / Nagranie / Fotografia / Grafika / Inne|
| Klient             | Relation     | → baza `Klienci`                               |
| Drive Folder URL   | URL          | Link do folderu w Drive lub Nextcloud          |
| Opis               | Rich Text    | Briefing od klienta                            |
| Deadline           | Date         | Termin realizacji                              |
| Log Czasu (min)    | Number       | Suma minut (Time Tracking z Adobe)             |
| Checklist          | Rich Text    | JSON: `[{ id, label, done }]`                  |

#### Statusy (w kolejności pipeline'u):
```
Nowe → W trakcie → W montażu → Oczekuje na materiały → Gotowe do akceptacji → Zaakceptowane → Archiwum
```

---

## Instalacja zależności

```bash
pnpm add @notionhq/client zod bcryptjs react-dropzone
pnpm add -D @types/bcryptjs
```

Dla NextAuth + Prisma (jeśli jeszcze nie masz):
```bash
pnpm add next-auth @auth/prisma-adapter @prisma/client
pnpm add -D prisma
```

---

## Konfiguracja Notion Integration

1. Wejdź na https://www.notion.so/my-integrations
2. Kliknij **New integration** → nadaj nazwę (np. "Freelancer Panel")
3. Zaznacz: Read content ✅, Update content ✅, Insert content ✅
4. Skopiuj **Internal Integration Token** → `NOTION_TOKEN` w `.env.local`
5. W każdej bazie Notion: **Share** → dodaj integrację jako connection

---

## Konfiguracja Google Drive (Service Account)

1. Google Cloud Console → APIs & Services → Enable **Drive API**
2. IAM → Service Accounts → Create Service Account
3. Keys → Add Key → JSON → pobierz plik
4. Skopiuj `client_email` → `GOOGLE_SERVICE_ACCOUNT_EMAIL`
5. Skopiuj `private_key` → `GOOGLE_PRIVATE_KEY`
6. Na Google Drive: utwórz folder nadrzędny → Share z adresem service account

---

## Adobe Premiere — API Reference

Wtyczka powinna wysyłać header: `Authorization: Bearer <ADOBE_API_SECRET>`

| Method | Endpoint                              | Opis                              |
|--------|---------------------------------------|-----------------------------------|
| GET    | `/api/adobe/tasks`                    | Lista zadań "W montażu"           |
| GET    | `/api/adobe/tasks?status=W trakcie`   | Filtruj po statusie               |
| GET    | `/api/adobe/tasks?klientId=<id>`      | Filtruj po kliencie               |
| PATCH  | `/api/adobe/tasks/:id/checklist`      | Zaktualizuj checklistę            |
| POST   | `/api/adobe/tasks/:id/timelog`        | Dodaj czas pracy                  |
| GET    | `/api/adobe/tasks/:id/timelog`        | Podgląd sumy czasu                |

### Przykład: POST timelog
```json
POST /api/adobe/tasks/abc123/timelog
Authorization: Bearer <ADOBE_API_SECRET>

{ "minuty": 45, "notatka": "Rough cut intro" }
```

---

## Następne kroki

- [ ] Utwórz `src/lib/auth.ts` (NextAuth z Prisma adapter)
- [ ] Utwórz `src/lib/prisma.ts` (Prisma singleton)
- [ ] Dodaj Prisma schema z modelem `User` (pole `role`)
- [ ] Podłącz `FileUploadZone` do strony projektu w dashboardzie klienta
- [ ] Utwórz `src/app/dashboard/projekty/page.tsx` z formularzem `createProject`
- [ ] Panel Admina: `/dashboard/admin` z listą zadań i zmianą statusów
