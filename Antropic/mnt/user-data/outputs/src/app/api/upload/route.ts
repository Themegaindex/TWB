/**
 * src/app/api/upload/route.ts
 * ─────────────────────────────────────────────────────────────────────────────
 * POST /api/upload
 * Przyjmuje multipart/form-data z polem "file" i "zadanieId".
 * Uploaduje plik na Google Drive (lub Nextcloud WebDAV) do folderu zadania.
 * Zwraca { url } – bezpośredni link do pliku.
 *
 * UWAGA: Next.js App Router parsuje FormData automatycznie.
 * Dla dużych plików rozważ: streaming upload lub presigned URLs.
 */

import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { getZadanieById } from "@/lib/notion";

export const maxDuration = 60; // Vercel: max 60s dla Hobby, 300s dla Pro

export async function POST(req: NextRequest) {
  // Auth
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  // Parsuj FormData
  let formData: FormData;
  try {
    formData = await req.formData();
  } catch {
    return NextResponse.json(
      { error: "Bad Request", message: "Nieprawidłowe dane formularza." },
      { status: 400 }
    );
  }

  const file = formData.get("file") as File | null;
  const zadanieId = formData.get("zadanieId") as string | null;

  if (!file || !zadanieId) {
    return NextResponse.json(
      { error: "Bad Request", message: "Brakujące pola: file, zadanieId." },
      { status: 400 }
    );
  }

  // Pobierz zadanie (walidacja i pobranie folderu)
  const zadanie = await getZadanieById(zadanieId);
  if (!zadanie) {
    return NextResponse.json(
      { error: "Not Found", message: "Zadanie nie istnieje." },
      { status: 404 }
    );
  }

  const provider = process.env.CLOUD_PROVIDER ?? "google";
  let fileUrl: string;

  try {
    if (provider === "nextcloud") {
      fileUrl = await uploadToNextcloud(file, zadanie.tytul);
    } else {
      fileUrl = await uploadToGoogleDrive(file, zadanieId, zadanie.driveFolderUrl);
    }
  } catch (err) {
    console.error("[POST /api/upload]", err);
    return NextResponse.json(
      {
        error: "Upload Failed",
        message: err instanceof Error ? err.message : "Błąd uploadu.",
      },
      { status: 500 }
    );
  }

  return NextResponse.json({ ok: true, url: fileUrl, name: file.name });
}

// ─── Google Drive Upload ──────────────────────────────────────────────────────

async function uploadToGoogleDrive(
  file: File,
  _zadanieId: string,
  parentFolderUrl: string | null
): Promise<string> {
  const email = process.env.GOOGLE_SERVICE_ACCOUNT_EMAIL!;
  const rawKey = process.env.GOOGLE_PRIVATE_KEY!;

  // Pobranie access tokena (re-użyj z lib/drive.ts w realnym projekcie)
  const { getGoogleAccessToken } = await import("@/lib/drive-internal");
  const token = await getGoogleAccessToken(email, rawKey.replace(/\\n/g, "\n"));

  // Wyciągnij folder ID z URL (jeśli dostępny)
  const parentId = parentFolderUrl
    ? parentFolderUrl.split("/folders/")[1]?.split("?")[0]
    : process.env.GOOGLE_DRIVE_PARENT_FOLDER;

  const arrayBuffer = await file.arrayBuffer();
  const bytes = new Uint8Array(arrayBuffer);

  // Multipart upload
  const boundary = "-------314159265358979323846";
  const delimiter = `\r\n--${boundary}\r\n`;
  const closeDelimiter = `\r\n--${boundary}--`;

  const metadata = JSON.stringify({
    name: file.name,
    ...(parentId && { parents: [parentId] }),
  });

  const metaPart =
    delimiter +
    "Content-Type: application/json; charset=UTF-8\r\n\r\n" +
    metadata;

  const filePart =
    `\r\n--${boundary}\r\nContent-Type: ${file.type || "application/octet-stream"}\r\n\r\n`;

  const metaBytes = new TextEncoder().encode(metaPart);
  const filePartBytes = new TextEncoder().encode(filePart);
  const closeBytes = new TextEncoder().encode(closeDelimiter);

  const body = new Uint8Array(
    metaBytes.length + filePartBytes.length + bytes.length + closeBytes.length
  );
  body.set(metaBytes, 0);
  body.set(filePartBytes, metaBytes.length);
  body.set(bytes, metaBytes.length + filePartBytes.length);
  body.set(closeBytes, metaBytes.length + filePartBytes.length + bytes.length);

  const uploadRes = await fetch(
    "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,webViewLink",
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": `multipart/related; boundary="${boundary}"`,
        "Content-Length": body.length.toString(),
      },
      body,
    }
  );

  if (!uploadRes.ok) {
    throw new Error(`Google Drive upload failed: ${await uploadRes.text()}`);
  }

  const { id, webViewLink } = (await uploadRes.json()) as {
    id: string;
    webViewLink: string;
  };

  // Ustaw publiczny dostęp (view-only)
  await fetch(`https://www.googleapis.com/drive/v3/files/${id}/permissions`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ role: "reader", type: "anyone" }),
  });

  return webViewLink;
}

// ─── Nextcloud WebDAV Upload ──────────────────────────────────────────────────

async function uploadToNextcloud(file: File, zadanieTytul: string): Promise<string> {
  const base = process.env.NEXTCLOUD_BASE_URL!;
  const user = process.env.NEXTCLOUD_USER!;
  const pass = process.env.NEXTCLOUD_PASSWORD!;
  const basePath = process.env.NEXTCLOUD_BASE_PATH ?? "/remote.php/dav/files/admin/Projekty";

  const sanitize = (s: string) => s.replace(/[/\\?%*:|"<>]/g, "-").trim().slice(0, 60);
  const folderPath = `${basePath}/${sanitize(zadanieTytul)}`;
  const filePath = `${folderPath}/${encodeURIComponent(file.name)}`;
  const davUrl = `${base}${filePath}`;
  const auth = Buffer.from(`${user}:${pass}`).toString("base64");

  const arrayBuffer = await file.arrayBuffer();

  const res = await fetch(davUrl, {
    method: "PUT",
    headers: {
      Authorization: `Basic ${auth}`,
      "Content-Type": file.type || "application/octet-stream",
    },
    body: arrayBuffer,
  });

  if (res.status !== 201 && res.status !== 204) {
    throw new Error(`Nextcloud upload failed: ${res.status}`);
  }

  // Zwróć link do przeglądarki pliku w Nextcloud
  const ncPath = filePath.replace("/remote.php/dav/files/admin", "");
  return `${base}/index.php/apps/files/?dir=${encodeURIComponent(ncPath)}`;
}
