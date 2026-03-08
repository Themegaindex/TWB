/**
 * src/lib/validations.ts
 * ─────────────────────────────────────────────────────────────────────────────
 * Wszystkie schematy Zod używane zarówno w Server Actions jak i route handlers.
 */

import { z } from "zod";

// ─── Auth ─────────────────────────────────────────────────────────────────────

export const RegisterSchema = z.object({
  imieNazwisko: z.string().min(2, "Imię i nazwisko musi mieć min. 2 znaki"),
  email: z.string().email("Nieprawidłowy adres email"),
  password: z
    .string()
    .min(8, "Hasło musi mieć min. 8 znaków")
    .regex(/[A-Z]/, "Hasło musi zawierać wielką literę")
    .regex(/[0-9]/, "Hasło musi zawierać cyfrę"),
  telefon: z.string().optional(),
  firma: z.string().optional(),
});

export type RegisterInput = z.infer<typeof RegisterSchema>;

export const LoginSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
});

export type LoginInput = z.infer<typeof LoginSchema>;

// ─── Projekt (Zadanie) ────────────────────────────────────────────────────────

export const CreateProjectSchema = z.object({
  tytul: z.string().min(3, "Tytuł musi mieć min. 3 znaki").max(200),
  typ: z.enum(["Montaż", "Nagranie", "Fotografia", "Grafika", "Inne"]),
  opis: z.string().max(2000).optional(),
  deadline: z
    .string()
    .regex(/^\d{4}-\d{2}-\d{2}$/, "Format daty: YYYY-MM-DD")
    .optional(),
});

export type CreateProjectInput = z.infer<typeof CreateProjectSchema>;

// ─── Adobe API ────────────────────────────────────────────────────────────────

export const AdobeChecklistUpdateSchema = z.object({
  checklist: z.array(
    z.object({
      id: z.string().uuid(),
      label: z.string().min(1).max(500),
      done: z.boolean(),
    })
  ),
});

export type AdobeChecklistUpdateInput = z.infer<
  typeof AdobeChecklistUpdateSchema
>;

export const AdobeTimelogSchema = z.object({
  minuty: z
    .number()
    .int("Minuty muszą być liczbą całkowitą")
    .positive("Minuty muszą być > 0")
    .max(1440, "Maksymalnie 1440 minut (24h) na jeden wpis"),
  notatka: z.string().max(500).optional(),
});

export type AdobeTimelogInput = z.infer<typeof AdobeTimelogSchema>;

// ─── Admin ────────────────────────────────────────────────────────────────────

export const UpdateZadanieStatusSchema = z.object({
  zadanieId: z.string().min(1),
  status: z.enum([
    "Nowe",
    "W trakcie",
    "W montażu",
    "Oczekuje na materiały",
    "Gotowe do akceptacji",
    "Zaakceptowane",
    "Archiwum",
  ]),
});

export type UpdateZadanieStatusInput = z.infer<
  typeof UpdateZadanieStatusSchema
>;

// ─── Utility ──────────────────────────────────────────────────────────────────

/** Bezpieczne parsowanie – zwraca `{ success, data }` lub `{ success, error }` */
export function safeParse<T>(
  schema: z.ZodSchema<T>,
  data: unknown
): { success: true; data: T } | { success: false; error: string } {
  const result = schema.safeParse(data);
  if (result.success) return { success: true, data: result.data };
  return {
    success: false,
    error: result.error.errors.map((e) => e.message).join(", "),
  };
}
