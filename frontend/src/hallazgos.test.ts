import { describe, expect, it } from 'vitest';
import { cajasDesdeBda, hallazgosDesdeBda, markdownDesdeBda } from './hallazgos';

// Forma real de explainability_info (recortada de una salida de BDA).
const custom = {
  explainability_info: [
    {
      nombre_completo: { confidence: 0.56, value: 'JESSICA CLAIRE', geometry: [{ page: 1 }] },
      linkedin: { confidence: 0.6, value: '' },
      habilidades_tecnicas: [
        { confidence: 0.59, value: 'R-Programming', geometry: [{ page: 1 }] },
        { confidence: 0.16, value: 'Linux' },
      ],
      experiencia: [
        {
          empresa: { confidence: 0.73, value: 'Konica Minolta', geometry: [{ page: 1 }] },
          cargo: { confidence: 0.52, value: 'Data Engineer' },
        },
      ],
      idiomas: [{ idioma: { confidence: 0.32, value: '' }, nivel: { confidence: 0.35, value: '' } }],
    },
  ],
};

describe('hallazgosDesdeBda', () => {
  const filas = hallazgosDesdeBda(custom);
  const fila = (id: string) => filas.find((f) => f.id === id)!;

  it('lee campo, valor, confianza y página de cada hoja', () => {
    expect(fila('nombre_completo')).toMatchObject({
      campo: 'Nombre completo',
      valor: 'JESSICA CLAIRE',
      confianza: 0.56,
      pagina: 1,
    });
  });

  it('agrupa listas y tablas con hijos y promedia su confianza', () => {
    const habilidades = fila('habilidades_tecnicas');
    expect(habilidades.hijos).toHaveLength(2);
    expect(habilidades.confianza).toBeCloseTo(0.375);
    const experiencia = fila('experiencia');
    expect(experiencia.hijos?.[0].campo).toBe('Fila 1');
    expect(experiencia.hijos?.[0].hijos?.map((h) => h.valor)).toEqual(['Konica Minolta', 'Data Engineer']);
  });

  it('una tabla con solo filas vacías queda sin hijos', () => {
    expect(fila('idiomas').hijos).toEqual([]);
  });

  it('tolera salidas vacías', () => {
    expect(hallazgosDesdeBda(null)).toEqual([]);
    expect(hallazgosDesdeBda({})).toEqual([]);
  });
});

describe('markdownDesdeBda', () => {
  it('prefiere el markdown del documento y si no, une las páginas', () => {
    expect(markdownDesdeBda({ document: { representation: { markdown: '# CV' } } })).toBe('# CV');
    expect(
      markdownDesdeBda({ pages: [{ representation: { markdown: 'a' } }, { representation: { markdown: 'b' } }] }),
    ).toBe('a\n\n---\n\nb');
    expect(markdownDesdeBda(null)).toBe('');
  });
});

describe('cajasDesdeBda', () => {
  const caja = { top: 0.1, left: 0.2, width: 0.3, height: 0.05 };
  const salida = {
    explainability_info: [
      {
        nombre_completo: { confidence: 0.8, value: 'Ana', geometry: [{ page: 1, boundingBox: caja }] },
        linkedin: { confidence: 0.6, value: '', geometry: [{ page: 1, boundingBox: caja }] },
        experiencia: [{ cargo: { confidence: 0.5, value: 'Dev', geometry: [{ page: 2, boundingBox: caja }] } }],
      },
    ],
  };

  it('saca una caja por geometría con página y nombre legible', () => {
    const cajas = cajasDesdeBda(salida);
    expect(cajas).toHaveLength(2);
    expect(cajas[0]).toMatchObject({ campo: 'Nombre completo', valor: 'Ana', pagina: 1, ...caja });
    expect(cajas[1]).toMatchObject({ campo: 'Experiencia 1 · Cargo', pagina: 2 });
  });

  it('omite campos vacíos y salidas sin explicabilidad', () => {
    expect(cajasDesdeBda(salida).some((c) => c.campo === 'LinkedIn')).toBe(false);
    expect(cajasDesdeBda(null)).toEqual([]);
  });
});
