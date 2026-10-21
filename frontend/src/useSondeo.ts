import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';

/**
 * Carga datos y los vuelve a pedir cada `intervaloMs` mientras `seguir(datos)` sea verdadero.
 * El demo no usa WebSockets: con sondeo cada pocos segundos basta.
 */
export function useSondeo<T>(cargar: () => Promise<T>, seguir: (datos: T) => boolean, intervaloMs = 3000) {
  const [datos, setDatos] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(true);
  const [version, setVersion] = useState(0);
  // Las funciones cambian en cada render; se guardan en refs para no reiniciar el ciclo.
  const cargarRef = useRef(cargar);
  const seguirRef = useRef(seguir);
  useLayoutEffect(() => {
    cargarRef.current = cargar;
    seguirRef.current = seguir;
  });

  useEffect(() => {
    let activo = true;
    let temporizador: number | undefined;
    const ciclo = async () => {
      try {
        const nuevos = await cargarRef.current();
        if (!activo) return;
        setDatos(nuevos);
        setError(null);
        if (seguirRef.current(nuevos)) temporizador = window.setTimeout(ciclo, intervaloMs);
      } catch (e) {
        if (activo) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (activo) setCargando(false);
      }
    };
    ciclo();
    return () => {
      activo = false;
      window.clearTimeout(temporizador);
    };
  }, [version, intervaloMs]);

  const refrescar = useCallback(() => setVersion((v) => v + 1), []);
  return { datos, error, cargando, refrescar };
}
