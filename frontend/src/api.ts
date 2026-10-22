import { fetchAuthSession } from 'aws-amplify/auth';
import type { DetalleDocumento, FilaDocumento } from './tipos';

let apiUrl = '';

export function configurarApi(url: string) {
  apiUrl = url.replace(/\/$/, '');
}

async function llamar<T>(ruta: string, opciones: RequestInit = {}): Promise<T> {
  const { tokens } = await fetchAuthSession();
  const token = tokens?.idToken?.toString();
  if (!token) throw new Error('La sesión expiró. Vuelve a iniciar sesión.');
  const respuesta = await fetch(`${apiUrl}${ruta}`, {
    ...opciones,
    headers: { ...opciones.headers, authorization: `Bearer ${token}`, 'content-type': 'application/json' },
  });
  const cuerpo = await respuesta.json().catch(() => ({}));
  if (!respuesta.ok) throw new Error(cuerpo.mensaje ?? `Error ${respuesta.status}`);
  return cuerpo as T;
}

export type Vista = 'mias' | 'todas';

export const listarDocumentos = (vista: Vista) =>
  llamar<{ documentos: FilaDocumento[] }>(`/cvs?vista=${vista}`).then((r) => r.documentos);

export const obtenerDocumento = (id: string) => llamar<DetalleDocumento>(`/cvs/${encodeURIComponent(id)}`);

async function descargarJson(url: string | null): Promise<unknown> {
  if (!url) return null;
  const respuesta = await fetch(url);
  if (!respuesta.ok) throw new Error(`S3 respondió ${respuesta.status} al descargar el JSON`);
  return respuesta.json();
}

/** La API solo firma las URLs; el JSON se descarga directo de S3 (sin límite de tamaño de la API). */
/** Figura que BDA recortó del documento (salida estándar), con URL prefirmada para verla. */
export interface ImagenExtraida {
  tipo: string;
  descripcion: string;
  pagina: number | null;
  url: string;
}

export async function obtenerCrudo(
  id: string,
): Promise<{ standard: unknown; custom: unknown; imagenes: ImagenExtraida[] }> {
  const urls = await llamar<{ standard: string | null; custom: string | null; imagenes?: ImagenExtraida[] }>(
    `/cvs/${encodeURIComponent(id)}/crudo`,
  );
  const [standard, custom] = await Promise.all([descargarJson(urls.standard), descargarJson(urls.custom)]);
  return { standard, custom, imagenes: urls.imagenes ?? [] };
}

/** Pide la URL prefirmada y sube el archivo directo a S3; el resto lo dispara EventBridge. */
export async function subirHojaDeVida(archivo: File): Promise<string> {
  const { documentoId, url, encabezados } = await llamar<{
    documentoId: string;
    url: string;
    encabezados: Record<string, string>;
  }>('/cvs', { method: 'POST', body: JSON.stringify({ nombreArchivo: archivo.name }) });
  const subida = await fetch(url, { method: 'PUT', headers: encabezados, body: archivo });
  if (!subida.ok) throw new Error(`S3 rechazó la subida (${subida.status})`);
  return documentoId;
}
