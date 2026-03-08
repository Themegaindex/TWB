/**
 * src/lib/drive.ts
 * ─────────────────────────────────────────────────────────────────────────────
 * Abstrakcja warstwy chmurowej: Google Drive API v3 lub Nextcloud (WebDAV).
 * Wybór backendu sterowany zmienną środowiskową CLOUD_PROVIDER.
 *
 * CLOUD_PROVIDER=google   → Google Drive Service Account
 * CLOUD_PROVIDER=nextcloud → Nextcloud WebDAV
 */

// ─── Typy ─────────────────────────────────────────────────────────────────────

export interface CloudFolder {
  id: string;
  name: string;
  url: string;
  provider: "google" | "nextcloud";
}

// ─── Dispatcher ───────────────────────────────────────────────────────────────

export async function createProjectFolder(
  klientNazwa: string,
  projektTytul: string
): Promise<CloudFolder> {
  const provider = process.env.CLOUD_PROVIDER ?? "google";

  const sanitize = (s: string) =>
    s.replace(/[/\\?%*:|"<>]/g, "-").trim().slice(0, 80);

  const folderName = `${sanitize(klientNazwa)} – ${sanitize(projektTytul)}`;

  if (provider === "nextcloud") {
    return createNextcloudFolder(folderName);
  }
  return createGoogleDriveFolder(folderName);
}

// ═══════════════════════════════════════════════════════════════════════════════
// GOOGLE DRIVE
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Tworzy folder na Google Drive używając Service Account (JWT).
 * Wymagane zmienne środowiskowe:
 *   GOOGLE_SERVICE_ACCOUNT_EMAIL
 *   GOOGLE_PRIVATE_KEY          (PEM, z \n jako separatorem)
 *   GOOGLE_DRIVE_PARENT_FOLDER  (ID folderu-rodzica, opcjonalne)
 */
async function createGoogleDriveFolder(
  folderName: string
): Promise<CloudFolder> {
  const email = process.env.GOOGLE_SERVICE_ACCOUNT_EMAIL;
  const rawKey = process.env.GOOGLE_PRIVATE_KEY;

  if (!email || !rawKey) {
    throw new Error(
      "Google Drive: brakujące zmienne GOOGLE_SERVICE_ACCOUNT_EMAIL / GOOGLE_PRIVATE_KEY"
    );
  }

  const token = await getGoogleAccessToken(email, rawKey.replace(/\\n/g, "\n"));

  const parentId = process.env.GOOGLE_DRIVE_PARENT_FOLDER;
  const body: Record<string, unknown> = {
    name: folderName,
    mimeType: "application/vnd.google-apps.folder",
    ...(parentId && { parents: [parentId] }),
  };

  const createRes = await fetch(
    "https://www.googleapis.com/drive/v3/files",
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    }
  );

  if (!createRes.ok) {
    const err = await createRes.text();
    throw new Error(`Google Drive: create folder failed – ${err}`);
  }

  const { id } = (await createRes.json()) as { id: string };

  // Nadaj uprawnienia "anyone with link can view"
  await fetch(
    `https://www.googleapis.com/drive/v3/files/${id}/permissions`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ role: "reader", type: "anyone" }),
    }
  );

  return {
    id,
    name: folderName,
    url: `https://drive.google.com/drive/folders/${id}`,
    provider: "google",
  };
}

// ─── JWT for Service Account ──────────────────────────────────────────────────

async function getGoogleAccessToken(
  clientEmail: string,
  privateKey: string
): Promise<string> {
  const now = Math.floor(Date.now() / 1000);
  const payload = {
    iss: clientEmail,
    scope: "https://www.googleapis.com/auth/drive",
    aud: "https://oauth2.googleapis.com/token",
    exp: now + 3600,
    iat: now,
  };

  // Importuj klucz i podpisz JWT
  const keyData = pemToArrayBuffer(privateKey);
  const cryptoKey = await crypto.subtle.importKey(
    "pkcs8",
    keyData,
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
    false,
    ["sign"]
  );

  const header = btoa(JSON.stringify({ alg: "RS256", typ: "JWT" }));
  const body = btoa(JSON.stringify(payload));
  const signingInput = `${header}.${body}`;

  const signature = await crypto.subtle.sign(
    "RSASSA-PKCS1-v1_5",
    cryptoKey,
    new TextEncoder().encode(signingInput)
  );

  const jwt = `${signingInput}.${arrayBufferToBase64(signature)}`;

  const tokenRes = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: `grant_type=urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Ajwt-bearer&assertion=${jwt}`,
  });

  if (!tokenRes.ok) {
    throw new Error(`Google OAuth: token fetch failed – ${await tokenRes.text()}`);
  }

  const { access_token } = (await tokenRes.json()) as { access_token: string };
  return access_token;
}

function pemToArrayBuffer(pem: string): ArrayBuffer {
  const b64 = pem
    .replace(/-----BEGIN PRIVATE KEY-----/, "")
    .replace(/-----END PRIVATE KEY-----/, "")
    .replace(/\s/g, "");
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes.buffer;
}

function arrayBufferToBase64(buffer: ArrayBuffer): string {
  return btoa(String.fromCharCode(...new Uint8Array(buffer)))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

// ═══════════════════════════════════════════════════════════════════════════════
// NEXTCLOUD (WebDAV)
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Tworzy folder na Nextcloud przez WebDAV MKCOL.
 * Wymagane zmienne środowiskowe:
 *   NEXTCLOUD_BASE_URL   (np. https://cloud.example.com)
 *   NEXTCLOUD_USER
 *   NEXTCLOUD_PASSWORD
 *   NEXTCLOUD_BASE_PATH  (np. /remote.php/dav/files/admin/Projekty)
 */
async function createNextcloudFolder(
  folderName: string
): Promise<CloudFolder> {
  const base = process.env.NEXTCLOUD_BASE_URL;
  const user = process.env.NEXTCLOUD_USER;
  const pass = process.env.NEXTCLOUD_PASSWORD;
  const basePath = process.env.NEXTCLOUD_BASE_PATH ?? "/remote.php/dav/files/admin/Projekty";

  if (!base || !user || !pass) {
    throw new Error("Nextcloud: brakujące zmienne NEXTCLOUD_BASE_URL / USER / PASSWORD");
  }

  const davUrl = `${base}${basePath}/${encodeURIComponent(folderName)}`;
  const auth = Buffer.from(`${user}:${pass}`).toString("base64");

  const res = await fetch(davUrl, {
    method: "MKCOL",
    headers: { Authorization: `Basic ${auth}` },
  });

  // 201 = Created, 405 = Already Exists (oba akceptujemy)
  if (res.status !== 201 && res.status !== 405) {
    throw new Error(
      `Nextcloud MKCOL failed: ${res.status} ${await res.text()}`
    );
  }

  const shareUrl = `${base}/index.php/apps/files/?dir=${encodeURIComponent(
    `${basePath.replace("/remote.php/dav/files/admin", "")}/${folderName}`
  )}`;

  return {
    id: folderName,
    name: folderName,
    url: shareUrl,
    provider: "nextcloud",
  };
}
