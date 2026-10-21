import { NOMBRES_CAMPO } from './formato';

/** Una fila de la tabla de hallazgos, como en la consola de BDA: campo, valor, confianza y página. */
export interface Hallazgo {
  id: string;
  campo: string;
  valor: string;
  confianza: number | null;
  pagina: number | null;
  hijos?: Hallazgo[];
}

type Hoja = { value?: unknown; confidence?: number; geometry?: { page?: number }[] };

const esHoja = (nodo: unknown): nodo is Hoja =>
  typeof nodo === 'object' && nodo !== null && !Array.isArray(nodo) && 'confidence' in nodo;

const etiqueta = (llave: string) =>
  NOMBRES_CAMPO[llave] ?? llave.replace(/_/g, ' ').replace(/^./, (l) => l.toUpperCase());

function valorTexto(valor: unknown): string {
  if (valor == null || valor === '') return '';
  return Array.isArray(valor) ? valor.join(', ') : String(valor);
}

function desdeHoja(id: string, campo: string, hoja: Hoja): Hallazgo {
  return {
    id,
    campo,
    valor: valorTexto(hoja.value),
    confianza: typeof hoja.confidence === 'number' ? hoja.confidence : null,
    pagina: hoja.geometry?.[0]?.page ?? null,
  };
}

/** Promedio de confianza de los hijos con valor, para la fila que agrupa una lista o tabla. */
function resumen(id: string, campo: string, hijos: Hallazgo[]): Hallazgo {
  const conValor = hijos.flatMap((h) => (h.hijos ? h.hijos : [h])).filter((h) => h.valor && h.confianza != null);
  const confianza = conValor.length ? conValor.reduce((s, h) => s + (h.confianza ?? 0), 0) / conValor.length : null;
  return { id, campo, valor: `${hijos.length} elemento${hijos.length === 1 ? '' : 's'}`, confianza, pagina: null, hijos };
}

function convertir(id: string, llave: string, nodo: unknown): Hallazgo | null {
  if (esHoja(nodo)) return desdeHoja(id, etiqueta(llave), nodo);
  if (Array.isArray(nodo)) {
    const hijos = nodo
      .map((item, i) => {
        const idHijo = `${id}[${i}]`;
        if (esHoja(item)) return desdeHoja(idHijo, `${i + 1}`, item);
        if (typeof item === 'object' && item !== null) {
          // Fila de una tabla del blueprint: cada columna es una hoja.
          const columnas = Object.entries(item)
            .map(([col, v]) => convertir(`${idHijo}.${col}`, col, v))
            .filter((h): h is Hallazgo => h !== null);
          // BDA devuelve una fila con celdas vacías cuando la tabla no está en el documento.
          return columnas.some((c) => c.valor !== '') ? resumen(idHijo, `Fila ${i + 1}`, columnas) : null;
        }
        return null;
      })
      .filter((h): h is Hallazgo => h !== null && h.valor !== '');
    return resumen(id, etiqueta(llave), hijos);
  }
  if (typeof nodo === 'object' && nodo !== null) {
    // Grupo de campos (custom type del blueprint).
    const hijos = Object.entries(nodo)
      .map(([k, v]) => convertir(`${id}.${k}`, k, v))
      .filter((h): h is Hallazgo => h !== null);
    return resumen(id, etiqueta(llave), hijos);
  }
  return null;
}

/** Convierte `explainability_info` de la salida personalizada de BDA en filas (con hijos para listas y tablas). */
export function hallazgosDesdeBda(custom: unknown): Hallazgo[] {
  const info = (custom as { explainability_info?: unknown[] } | null)?.explainability_info;
  const bloque = Array.isArray(info) ? info[0] : null;
  if (!bloque || typeof bloque !== 'object') return [];
  return Object.entries(bloque as Record<string, unknown>)
    .map(([llave, nodo]) => convertir(llave, llave, nodo))
    .filter((h): h is Hallazgo => h !== null);
}

/** Caja de un campo sobre la página, en fracciones (0 a 1) del ancho y alto de la página. */
export interface Caja {
  id: string;
  campo: string;
  valor: string;
  confianza: number | null;
  pagina: number;
  top: number;
  left: number;
  width: number;
  height: number;
}

type Geometria = { page?: number; boundingBox?: { top: number; left: number; width: number; height: number } };

/** Todas las cajas de la salida personalizada de BDA (una por fragmento de texto de cada campo). */
export function cajasDesdeBda(custom: unknown): Caja[] {
  const info = (custom as { explainability_info?: unknown[] } | null)?.explainability_info;
  const bloque = Array.isArray(info) ? info[0] : null;
  const cajas: Caja[] = [];
  const recorrer = (nodo: unknown, ruta: string, campo: string) => {
    if (esHoja(nodo)) {
      const valor = valorTexto(nodo.value);
      ((nodo.geometry ?? []) as Geometria[]).forEach((g, i) => {
        if (!g.boundingBox || !valor) return;
        cajas.push({
          id: `${ruta}#${i}`,
          campo,
          valor,
          confianza: typeof nodo.confidence === 'number' ? nodo.confidence : null,
          pagina: g.page ?? 1,
          ...g.boundingBox,
        });
      });
      return;
    }
    if (Array.isArray(nodo)) nodo.forEach((item, i) => recorrer(item, `${ruta}[${i}]`, `${campo} ${i + 1}`));
    else if (typeof nodo === 'object' && nodo !== null)
      Object.entries(nodo).forEach(([k, v]) => recorrer(v, ruta ? `${ruta}.${k}` : k, ruta ? `${campo} · ${etiqueta(k)}` : etiqueta(k)));
  };
  if (bloque && typeof bloque === 'object') recorrer(bloque, '', '');
  return cajas;
}

/** Markdown del documento completo en la salida estándar (o la unión de las páginas si no viene). */
export function markdownDesdeBda(standard: unknown): string {
  const s = standard as {
    document?: { representation?: { markdown?: string } };
    pages?: { representation?: { markdown?: string } }[];
  } | null;
  const documento = s?.document?.representation?.markdown;
  if (documento) return documento;
  return (s?.pages ?? [])
    .map((p) => p.representation?.markdown ?? '')
    .filter(Boolean)
    .join('\n\n---\n\n');
}
