import Box from '@cloudscape-design/components/box';
import Button from '@cloudscape-design/components/button';
import Header from '@cloudscape-design/components/header';
import Link from '@cloudscape-design/components/link';
import SegmentedControl from '@cloudscape-design/components/segmented-control';
import Table from '@cloudscape-design/components/table';
import TextFilter, { type TextFilterProps } from '@cloudscape-design/components/text-filter';
import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router';
import { listarDocumentos, type Vista } from '../api';
import { Confianza, EstadoDocumento } from '../componentes';
import { esBilingue, fechaHora, limpiarLista, texto, usd } from '../formato';
import Badge from '@cloudscape-design/components/badge';
import SpaceBetween from '@cloudscape-design/components/space-between';
import type { FilaDocumento } from '../tipos';
import { useSondeo } from '../useSondeo';

type Filtro = 'todos' | 'PENDIENTE' | 'PROCESADO' | 'FALLIDO';

const TEXTOS: Record<Vista, { titulo: string; descripcion: string }> = {
  mias: { titulo: 'Mis hojas de vida', descripcion: 'Las hojas de vida que subiste y su análisis.' },
  todas: {
    titulo: 'Todas las candidaturas',
    descripcion: 'Vista del equipo de reclutamiento: todas las corridas, incluidas las anteriores.',
  },
};

export default function Analisis({ vista }: { vista: Vista }) {
  const navegar = useNavigate();
  const [filtro, setFiltro] = useState<Filtro>('todos');
  const [busqueda, setBusqueda] = useState('');
  // Mientras haya algo pendiente se refresca cada 3 s; si no, se queda quieta.
  const { datos, error, cargando, refrescar } = useSondeo(() => listarDocumentos(vista), (filas) =>
    filas.some((f) => f.estado === 'PENDIENTE'),
  );

  const filas = useMemo(() => {
    const termino = busqueda.toLowerCase();
    return (datos ?? []).filter(
      (f) =>
        (filtro === 'todos' || f.estado === filtro) &&
        [f.nombre_completo, f.nombreOriginal, f.area_profesional, f.nivel_seniority, ...(f.habilidadesTop ?? []), ...(f.idiomasEstimados ?? [])]
          .join(' ')
          .toLowerCase()
          .includes(termino),
    );
  }, [datos, filtro, busqueda]);

  return (
    <Table<FilaDocumento>
      variant="full-page"
      loading={cargando}
      loadingText="Cargando análisis"
      items={filas}
      trackBy="documentoId"
      stickyHeader
      wrapLines
      header={
        <Header
          variant="awsui-h1-sticky"
          counter={`(${datos?.length ?? 0})`}
          description={TEXTOS[vista].descripcion}
          actions={
            <Button iconName="refresh" onClick={refrescar}>
              Actualizar
            </Button>
          }
        >
          {TEXTOS[vista].titulo}
        </Header>
      }
      filter={
        <Box>
          <TextFilter
            filteringText={busqueda}
            filteringPlaceholder="Buscar por nombre, área, seniority, habilidad o idioma"
            onChange={({ detail }: { detail: TextFilterProps.ChangeDetail }) => setBusqueda(detail.filteringText)}
          />
          <Box margin={{ top: 's' }}>
            <SegmentedControl
              selectedId={filtro}
              onChange={({ detail }) => setFiltro(detail.selectedId as Filtro)}
              options={[
                { id: 'todos', text: 'Todos' },
                { id: 'PENDIENTE', text: 'Pendientes' },
                { id: 'PROCESADO', text: 'Procesados' },
                { id: 'FALLIDO', text: 'Fallidos' },
              ]}
            />
          </Box>
        </Box>
      }
      empty={
        <Box textAlign="center" color="inherit">
          {error ? `No pudimos cargar los análisis: ${error}` : 'Todavía no hay hojas de vida analizadas.'}
        </Box>
      }
      resizableColumns
      columnDefinitions={[
        { id: 'estado', header: 'Estado', minWidth: 130, cell: (f) => <EstadoDocumento estado={f.estado} /> },
        {
          id: 'nombre',
          header: 'Persona candidata',
          minWidth: 220,
          cell: (f) => (
            <Link onFollow={() => navegar(`/hojas-de-vida/${f.documentoId}`)}>
              {f.nombre_completo || f.nombreOriginal}
            </Link>
          ),
        },
        { id: 'titulo', header: 'Título', minWidth: 200, cell: (f) => texto(f.titulo_profesional) },
        { id: 'area', header: 'Área', minWidth: 140, cell: (f) => texto(f.area_profesional) },
        { id: 'seniority', header: 'Seniority', minWidth: 120, cell: (f) => texto(f.nivel_seniority) },
        { id: 'anios', header: 'Años', minWidth: 80, cell: (f) => texto(f.anios_experiencia) },
        { id: 'habilidades', header: 'Habilidades top', minWidth: 220, cell: (f) => texto(f.habilidadesTop) },
        {
          id: 'idiomas',
          header: 'Idiomas estimados',
          minWidth: 200,
          cell: (f) => (
            <SpaceBetween direction="horizontal" size="xs">
              <span>{texto(limpiarLista(f.idiomasEstimados))}</span>
              {esBilingue(f.idiomasEstimados) && <Badge color="blue">Posible bilingüe</Badge>}
            </SpaceBetween>
          ),
        },
        { id: 'confianza', header: 'Confianza mínima', minWidth: 140, cell: (f) => <Confianza valor={f.confianzaMin} /> },
        { id: 'paginas', header: 'Páginas', minWidth: 90, cell: (f) => texto(f.paginas) },
        { id: 'costo', header: 'Costo estimado', minWidth: 130, cell: (f) => usd(f.costoEstimadoUsd) },
        { id: 'segundos', header: 'Segundos', minWidth: 100, cell: (f) => texto(f.segundosTotales) },
        { id: 'fecha', header: 'Subido', minWidth: 180, cell: (f) => fechaHora(f.creadoEn) },
      ]}
    />
  );
}
