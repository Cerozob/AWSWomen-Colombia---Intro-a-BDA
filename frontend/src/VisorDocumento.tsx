import Box from '@cloudscape-design/components/box';
import Link from '@cloudscape-design/components/link';
import SpaceBetween from '@cloudscape-design/components/space-between';
import Spinner from '@cloudscape-design/components/spinner';
import * as pdfjs from 'pdfjs-dist';
import urlTrabajador from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import { useCallback, useEffect, useRef, useState } from 'react';
import { COLOR_NIVEL, nivelConfianza } from './formato';
import type { Caja } from './hallazgos';
import { useConfig } from './componentes';

// pdfjs-dist queda fijo en 5.4.624: desde 5.5 usa Map.getOrInsertComputed, que muchos navegadores
// aún no tienen ("getOrInsertComputed is not a function" y la página queda en blanco).
pdfjs.GlobalWorkerOptions.workerSrc = urlTrabajador;

const ALTO_PANEL = '75vh';
const COLORES: Record<string, string> = { green: '#037f0c', 'severity-medium': '#b65c00', red: '#d91515' };

/** Cajas de BDA sobre una página. Las coordenadas vienen en fracciones de la página, así que escalan solas. */
function Capa({ cajas }: { cajas: Caja[] }) {
  const { confianza: umbrales } = useConfig();
  return (
    <>
      {cajas.map((c) => {
        const color = c.confianza == null ? '#0972d3' : COLORES[COLOR_NIVEL[nivelConfianza(c.confianza, umbrales)]];
        return (
          <div
            key={c.id}
            title={`${c.campo}: ${c.valor}`}
            style={{
              position: 'absolute',
              top: `${c.top * 100}%`,
              left: `${c.left * 100}%`,
              width: `${c.width * 100}%`,
              height: `${c.height * 100}%`,
              border: `2px solid ${color}`,
              background: `${color}22`,
              borderRadius: 2,
              cursor: 'help',
            }}
          />
        );
      })}
    </>
  );
}

// Escala fija: el canvas se dibuja a buena resolución y CSS lo ajusta al ancho del panel.
// Así el dibujo no depende de que el panel ya tenga ancho cuando se monta.
const ESCALA_PDF = 2;

/** Dibuja una página de PDF en un canvas y pone encima sus cajas. Avisa si el dibujo falla. */
function PaginaPdf({
  documento,
  numero,
  cajas,
  alFallar,
}: {
  documento: pdfjs.PDFDocumentProxy;
  numero: number;
  cajas: Caja[];
  alFallar: (motivo: string) => void;
}) {
  const lienzo = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    let tarea: pdfjs.RenderTask | undefined;
    let activo = true;
    documento
      .getPage(numero)
      .then((pagina) => {
        const canvas = lienzo.current;
        if (!activo || !canvas) return;
        const vista = pagina.getViewport({ scale: ESCALA_PDF });
        canvas.width = Math.floor(vista.width);
        canvas.height = Math.floor(vista.height);
        tarea = pagina.render({ canvas, viewport: vista });
        return tarea.promise;
      })
      .catch((e: Error) => {
        if (activo && e?.name !== 'RenderingCancelledException') alFallar(e?.message ?? String(e));
      });
    return () => {
      activo = false;
      tarea?.cancel();
    };
  }, [documento, numero, alFallar]);

  return (
    <div style={{ position: 'relative', marginBottom: 12, boxShadow: '0 1px 4px #0003', background: '#fff' }}>
      <canvas ref={lienzo} style={{ width: '100%', display: 'block' }} />
      <Capa cajas={cajas} />
    </div>
  );
}

function VisorPdf({ url, nombre, cajas }: { url: string; nombre: string; cajas: Caja[] }) {
  const [documento, setDocumento] = useState<pdfjs.PDFDocumentProxy | null>(null);
  const [fallo, setFallo] = useState<string | null>(null);
  const alFallar = useCallback((motivo: string) => setFallo((previo) => previo ?? motivo), []);

  useEffect(() => {
    // Archivo completo en una sola descarga: las hojas de vida son pequeñas y así no dependemos
    // de peticiones por rangos (Range) contra S3 con CORS.
    const carga = pdfjs.getDocument({ url, disableRange: true, disableStream: true, disableAutoFetch: true });
    carga.promise.then(setDocumento).catch((e: Error) => alFallar(e.message));
    return () => {
      carga.destroy();
    };
  }, [url, alFallar]);

  if (fallo) {
    // Respaldo: el visor de PDF del navegador (sin cajas) para que la demo no se quede en blanco.
    return (
      <SpaceBetween size="xs">
        <Box color="text-status-warning" fontSize="body-s">
          No se pudieron dibujar las cajas ({fallo}). Se muestra el visor del navegador.
        </Box>
        <iframe title={nombre} src={url} style={{ width: '100%', height: ALTO_PANEL, border: 0 }} />
      </SpaceBetween>
    );
  }
  if (!documento) return <Spinner size="large" />;
  return (
    <div style={{ maxHeight: ALTO_PANEL, overflow: 'auto' }}>
      {Array.from({ length: documento.numPages }, (_, i) => i + 1).map((n) => (
        <PaginaPdf
          key={n}
          documento={documento}
          numero={n}
          cajas={cajas.filter((c) => c.pagina === n)}
          alFallar={alFallar}
        />
      ))}
    </div>
  );
}

/**
 * Vista previa del archivo original (URL prefirmada) con las cajas que devolvió BDA.
 * Se fija la primera URL para que el sondeo del detalle no recargue el visor.
 */
export default function VisorDocumento({
  url,
  tipo,
  nombre,
  cajas,
}: {
  url: string;
  tipo?: string;
  nombre: string;
  cajas: Caja[];
}) {
  const [src] = useState(url);
  if (tipo === 'application/pdf') return <VisorPdf url={src} nombre={nombre} cajas={cajas} />;
  if (tipo?.startsWith('image/') && tipo !== 'image/tiff') {
    return (
      <div style={{ maxHeight: ALTO_PANEL, overflow: 'auto' }}>
        <div style={{ position: 'relative' }}>
          <img src={src} alt={nombre} style={{ width: '100%', display: 'block' }} />
          <Capa cajas={cajas.filter((c) => c.pagina === 1)} />
        </div>
      </div>
    );
  }
  return (
    <Box textAlign="center" padding="xl" color="text-body-secondary">
      <SpaceBetween size="s">
        <span>El navegador no puede mostrar este formato (DOCX o TIFF).</span>
        <Link external href={src}>
          Descargar el archivo original
        </Link>
      </SpaceBetween>
    </Box>
  );
}
