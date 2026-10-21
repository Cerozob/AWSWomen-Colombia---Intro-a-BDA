export type Estado = 'PENDIENTE' | 'PROCESADO' | 'FALLIDO';

export interface ConfigWeb {
  region: string;
  apiUrl: string;
  userPoolId: string;
  userPoolClientId: string;
  dominioLogin: string;
  urlSitio: string;
  confianza: { alta: number; media: number };
  consolaStepFunctions: string;
}

export interface EventoHistorial {
  etapa: string;
  en: string;
}

export interface FilaDocumento {
  documentoId: string;
  nombreOriginal: string;
  email: string;
  estado: Estado;
  etapa: string;
  creadoEn: string;
  paginas?: number | null;
  segundosTotales?: number | null;
  costoEstimadoUsd?: number | null;
  motivo?: string | null;
  nombre_completo?: string | null;
  titulo_profesional?: string | null;
  area_profesional?: string | null;
  nivel_seniority?: string | null;
  anios_experiencia?: number | null;
  habilidadesTop?: string[];
  idiomasEstimados?: string[];
  confianzaMin?: number | null;
}

export interface Seguimiento {
  documentoId: string;
  nombreOriginal: string;
  email: string;
  estado: Estado;
  etapa: string;
  historial: EventoHistorial[];
  creadoEn: string;
  paginas?: number;
  costoEstimadoUsd?: number;
  segundosTotales?: number;
  vueltasSondeo?: number;
  ejecucionArn?: string;
  motivo?: string;
  s3Key?: string;
  tipo?: string;
}

export type Fila = Record<string, string | number | null | undefined>;

export interface CamposCv {
  nombre_completo?: string;
  email?: string;
  telefono?: string;
  ubicacion?: string;
  linkedin?: string;
  titulo_profesional?: string;
  area_profesional?: string;
  otros_enlaces?: string[];
  logros_cuantificables?: string[];
  idioma_documento?: string;
  anios_experiencia?: number;
  nivel_seniority?: string;
  habilidades_tecnicas?: string[];
  habilidades_blandas?: string[];
  certificaciones?: string[];
  idiomas_estimados?: string[];
  idiomas?: Fila[];
  experiencia?: Fila[];
  educacion?: Fila[];
  resumen_perfil?: string;
}

export interface Resultado {
  documentoId: string;
  camposPersonalizados: CamposCv;
  confianza: Record<string, number>;
  camposARevisar: string[];
  confianzaMin: number | null;
  blueprintCoincidente: { nombre: string; confianza: number | null; estado: string | null };
  salidaEstandar: { resumenDocumento: string; paginas: number; tablasDetectadas: number; modalidad: string };
  costoEstimadoUsd: number;
}

export interface DetalleDocumento {
  seguimiento: Seguimiento;
  resultado: Resultado | null;
  urlArchivo?: string | null;
  urlDescarga?: string | null;
}
