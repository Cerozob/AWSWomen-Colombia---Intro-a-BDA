import type { StatusIndicatorProps } from '@cloudscape-design/components/status-indicator';
import type { Estado } from './tipos';

export type NivelConfianza = 'Alta' | 'Media' | 'Baja';

/** La app no muestra el número crudo de confianza: lo traduce a una escala de tres niveles. */
export function nivelConfianza(valor: number, umbrales: { alta: number; media: number }): NivelConfianza {
  if (valor >= umbrales.alta) return 'Alta';
  if (valor >= umbrales.media) return 'Media';
  return 'Baja';
}

export const COLOR_NIVEL: Record<NivelConfianza, 'green' | 'severity-medium' | 'red'> = {
  Alta: 'green',
  Media: 'severity-medium',
  Baja: 'red',
};

export const ESTADOS: Record<Estado, { texto: string; tipo: StatusIndicatorProps.Type }> = {
  PENDIENTE: { texto: 'Pendiente', tipo: 'in-progress' },
  PROCESADO: { texto: 'Procesado', tipo: 'success' },
  FALLIDO: { texto: 'Fallido', tipo: 'error' },
};

export const ETAPAS: Record<string, string> = {
  SUBIDO: 'Archivo subido',
  VALIDADO: 'Validado',
  EN_BDA: 'Procesando en BDA',
  PROCESADO: 'Procesado',
  FALLIDO: 'Fallido',
};

export const NOMBRES_CAMPO: Record<string, string> = {
  nombre_completo: 'Nombre completo',
  email: 'Correo',
  telefono: 'Teléfono',
  ubicacion: 'Ubicación',
  linkedin: 'LinkedIn',
  titulo_profesional: 'Título profesional',
  area_profesional: 'Área profesional',
  otros_enlaces: 'Otros enlaces',
  logros_cuantificables: 'Logros medibles',
  idioma_documento: 'Idioma del documento',
  anios_experiencia: 'Años de experiencia',
  nivel_seniority: 'Seniority',
  habilidades_tecnicas: 'Habilidades técnicas',
  habilidades_blandas: 'Habilidades blandas',
  certificaciones: 'Certificaciones',
  idiomas_estimados: 'Idiomas estimados',
  idiomas: 'Idiomas',
  experiencia: 'Experiencia',
  educacion: 'Educación',
  resumen_perfil: 'Resumen del perfil',
};

export function fechaHora(iso?: string): string {
  if (!iso) return '-';
  return new Date(iso).toLocaleString('es-CO', { dateStyle: 'short', timeStyle: 'medium' });
}

export function usd(valor?: number | null): string {
  return valor == null ? '-' : `USD ${valor.toFixed(3)}`;
}

/** Quita vacíos y repetidos (sin importar mayúsculas): BDA a veces devuelve [""] o duplicados. */
export function limpiarLista(valores?: string[] | null): string[] {
  const vistos = new Set<string>();
  return (valores ?? []).filter((v) => {
    const clave = v?.trim().toLowerCase();
    if (!clave || vistos.has(clave)) return false;
    vistos.add(clave);
    return true;
  });
}

/** Posible bilingüe: BDA estimó dos o más idiomas (por el documento y por la ubicación). */
export function esBilingue(idiomas?: string[] | null): boolean {
  return limpiarLista(idiomas).length >= 2;
}

export function texto(valor: unknown): string {
  if (valor == null || valor === '') return '-';
  return Array.isArray(valor) ? valor.join(', ') : String(valor);
}
