/**
 * src/components/FileUploadZone.tsx
 * ─────────────────────────────────────────────────────────────────────────────
 * Drag & Drop upload komponent.
 * Przesyła pliki do `/api/upload` (route handler), który zapisuje je
 * na Google Drive / Nextcloud i zwraca URL.
 *
 * Użycie:
 *   <FileUploadZone zadanieId="notion-page-id" onUploadComplete={(url) => ...} />
 */

"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

// ─── Typy ─────────────────────────────────────────────────────────────────────

interface UploadedFile {
  name: string;
  url: string;
  size: number;
}

interface FileUploadZoneProps {
  zadanieId: string;
  onUploadComplete?: (files: UploadedFile[]) => void;
  accept?: Record<string, string[]>;
  maxFiles?: number;
  maxSizeMB?: number;
}

// ─── Component ────────────────────────────────────────────────────────────────

export function FileUploadZone({
  zadanieId,
  onUploadComplete,
  accept = {
    "video/*": [".mp4", ".mov", ".avi", ".mxf", ".r3d"],
    "image/*": [".jpg", ".jpeg", ".png", ".tif", ".tiff", ".arw", ".cr3"],
    "audio/*": [".wav", ".mp3", ".aac"],
    "application/zip": [".zip"],
  },
  maxFiles = 20,
  maxSizeMB = 2048, // 2GB
}: FileUploadZoneProps) {
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [uploaded, setUploaded] = useState<UploadedFile[]>([]);
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      if (acceptedFiles.length === 0) return;
      setError(null);
      setUploading(true);
      setProgress(0);

      const results: UploadedFile[] = [];

      for (let i = 0; i < acceptedFiles.length; i++) {
        const file = acceptedFiles[i];
        const formData = new FormData();
        formData.append("file", file);
        formData.append("zadanieId", zadanieId);

        try {
          const res = await fetch("/api/upload", {
            method: "POST",
            body: formData,
          });

          if (!res.ok) {
            const { message } = await res.json();
            throw new Error(message ?? `Upload failed: ${res.status}`);
          }

          const { url } = (await res.json()) as { url: string };
          results.push({ name: file.name, url, size: file.size });
        } catch (err) {
          setError(
            err instanceof Error ? err.message : "Nieznany błąd uploadu."
          );
          break;
        }

        setProgress(Math.round(((i + 1) / acceptedFiles.length) * 100));
      }

      setUploaded((prev) => [...prev, ...results]);
      setUploading(false);
      onUploadComplete?.(results);
    },
    [zadanieId, onUploadComplete]
  );

  const { getRootProps, getInputProps, isDragActive, fileRejections } =
    useDropzone({
      onDrop,
      accept,
      maxFiles,
      maxSize: maxSizeMB * 1024 * 1024,
      disabled: uploading,
    });

  const formatSize = (bytes: number) => {
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
    return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
  };

  return (
    <div className="space-y-4">
      {/* Drop Zone */}
      <div
        {...getRootProps()}
        className={cn(
          "border-2 border-dashed rounded-xl p-10 text-center transition-colors cursor-pointer",
          isDragActive
            ? "border-primary bg-primary/5"
            : "border-muted-foreground/25 hover:border-primary/50 hover:bg-muted/30",
          uploading && "opacity-60 cursor-not-allowed"
        )}
      >
        <input {...getInputProps()} />

        <div className="flex flex-col items-center gap-3">
          <UploadIcon className="h-10 w-10 text-muted-foreground" />

          {isDragActive ? (
            <p className="text-lg font-medium text-primary">
              Upuść pliki tutaj…
            </p>
          ) : (
            <>
              <p className="text-base font-medium">
                Przeciągnij i upuść pliki
              </p>
              <p className="text-sm text-muted-foreground">
                lub kliknij aby wybrać • Maks. {maxFiles} plików •{" "}
                {maxSizeMB >= 1024 ? `${maxSizeMB / 1024}GB` : `${maxSizeMB}MB`}{" "}
                na plik
              </p>
              <p className="text-xs text-muted-foreground">
                MP4, MOV, MXF, R3D, JPG, TIFF, ARW, CR3, WAV…
              </p>
            </>
          )}
        </div>
      </div>

      {/* Błędy walidacji drop zone */}
      {fileRejections.length > 0 && (
        <div className="text-sm text-destructive space-y-1">
          {fileRejections.map(({ file, errors }) => (
            <p key={file.name}>
              <span className="font-medium">{file.name}</span>:{" "}
              {errors.map((e) => e.message).join(", ")}
            </p>
          ))}
        </div>
      )}

      {/* Błąd uploadowy */}
      {error && (
        <p className="text-sm text-destructive font-medium">⚠ {error}</p>
      )}

      {/* Progress */}
      {uploading && (
        <div className="space-y-2">
          <div className="flex justify-between text-sm text-muted-foreground">
            <span>Wysyłanie…</span>
            <span>{progress}%</span>
          </div>
          <Progress value={progress} />
        </div>
      )}

      {/* Lista wgranych plików */}
      {uploaded.length > 0 && (
        <div className="space-y-2">
          <p className="text-sm font-medium text-muted-foreground">
            Wgrane pliki ({uploaded.length})
          </p>
          <ul className="space-y-1">
            {uploaded.map((f) => (
              <li
                key={f.url}
                className="flex items-center justify-between rounded-lg border px-3 py-2 text-sm"
              >
                <span className="truncate max-w-xs">{f.name}</span>
                <div className="flex items-center gap-2 shrink-0 ml-2">
                  <Badge variant="secondary">{formatSize(f.size)}</Badge>
                  <Button variant="ghost" size="sm" asChild>
                    <a href={f.url} target="_blank" rel="noopener noreferrer">
                      Otwórz
                    </a>
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// ─── Icon ─────────────────────────────────────────────────────────────────────

function UploadIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={1.5}
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M12 16.5V9.75m0 0-3 3m3-3 3 3M6.75 19.5a4.5 4.5 0 0 1-1.41-8.775 5.25 5.25 0 0 1 10.338-2.32 5.75 5.75 0 0 1 1.018 11.095"
      />
    </svg>
  );
}
