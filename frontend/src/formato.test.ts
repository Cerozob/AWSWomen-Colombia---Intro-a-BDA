import { describe, expect, it } from 'vitest';
import { esBilingue, limpiarLista, nivelConfianza, texto, usd } from './formato';

describe('idiomas estimados', () => {
  it('limpia vacíos y repetidos', () => {
    expect(limpiarLista(['inglés', '', 'Inglés', 'español'])).toEqual(['inglés', 'español']);
    expect(limpiarLista(undefined)).toEqual([]);
  });
  it('marca posible bilingüe con dos idiomas distintos', () => {
    expect(esBilingue(['inglés', 'español'])).toBe(true);
    expect(esBilingue(['inglés', 'Inglés'])).toBe(false);
    expect(esBilingue([''])).toBe(false);
  });
});

const umbrales = { alta: 0.8, media: 0.5 };

describe('nivelConfianza', () => {
  it('usa los umbrales inclusivos', () => {
    expect(nivelConfianza(0.8, umbrales)).toBe('Alta');
    expect(nivelConfianza(0.79, umbrales)).toBe('Media');
    expect(nivelConfianza(0.5, umbrales)).toBe('Media');
    expect(nivelConfianza(0.49, umbrales)).toBe('Baja');
  });
});

describe('formato', () => {
  it('muestra guion cuando no hay valor', () => {
    expect(texto(null)).toBe('-');
    expect(usd(undefined)).toBe('-');
  });
  it('une listas y formatea costo', () => {
    expect(texto(['AWS', 'Python'])).toBe('AWS, Python');
    expect(usd(0.08)).toBe('USD 0.080');
  });
});
