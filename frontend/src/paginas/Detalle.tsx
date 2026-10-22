import Alert from '@cloudscape-design/components/alert';
import Badge from '@cloudscape-design/components/badge';
import Box from '@cloudscape-design/components/box';
import Button from '@cloudscape-design/components/button';
import ColumnLayout from '@cloudscape-design/components/column-layout';
import Container from '@cloudscape-design/components/container';
import Grid from '@cloudscape-design/components/grid';
import ContentLayout from '@cloudscape-design/components/content-layout';
import Header from '@cloudscape-design/components/header';
import KeyValuePairs from '@cloudscape-design/components/key-value-pairs';
import Link from '@cloudscape-design/components/link';
import SegmentedControl from '@cloudscape-design/components/segmented-control';
import SpaceBetween from '@cloudscape-design/components/space-between';
import Spinner from '@cloudscape-design/components/spinner';
import Steps, { type StepsProps } from '@cloudscape-design/components/steps';
import Table from '@cloudscape-design/components/table';
import Tabs from '@cloudscape-design/components/tabs';
import Toggle, { type ToggleProps } from '@cloudscape-design/components/toggle';
import CodeView from '@cloudscape-design/code-view/code-view';
import { useState } from 'react';
import { useParams } from 'react-router';
import { obtenerCrudo, obtenerDocumento, type ImagenExtraida } from '../api';
import { Confianza, EstadoDocumento, useConfig } from '../componentes';
import { ETAPAS, NOMBRES_CAMPO, esBilingue, fechaHora, limpiarLista, texto, usd } from '../formato';
import { cajasDesdeBda, hallazgosDesdeBda, markdownDesdeBda, type Hallazgo } from '../hallazgos';
import VisorDocumento from '../VisorDocumento';
import type { DetalleDocumento, Fila, Resultado, Seguimiento } from '../tipos';
import { useSondeo } from '../useSondeo';

function Etiquetas({ valores }: { valores?: string[] }) {
  const limpios = limpiarLista(valores);
  if (!limpios.length) return <>-</>;
  return (
    <SpaceBetween direction="horizontal" size="xs">
      {limpios.map((v) => (
        <Badge key={v}>{v}</Badge>
      ))}
    </SpaceBetween>
  );
}

function TablaFilas({ titulo, filas, columnas }: { titulo: string; filas?: Fila[]; columnas: string[] }) {
  return (
    <Table<Fila>
      header={<Header variant="h3">{titulo}</Header>}
      // BDA devuelve una fila vacía cuando la tabla no aparece en el documento.
      items={(filas ?? []).filter((f) => columnas.some((c) => f[c] != null && f[c] !== ''))}
      wrapLines
      empty={<Box color="text-status-inactive">Sin datos</Box>}
      columnDefinitions={columnas.map((c) => ({
        id: c,
        header: c.replace(/_/g, ' ').replace(/^./, (l) => l.toUpperCase()),
        cell: (f: Fila) => texto(f[c]),
      }))}
    />
  );
}

function LineaDeTiempo({ seguimiento }: { seguimiento: Seguimiento }) {
  const eventos = seguimiento.historial ?? [];
  const pasos: StepsProps.Step[] = eventos.map((e, i) => {
    const ultimo = i === eventos.length - 1;
    const enCurso = ultimo && seguimiento.estado === 'PENDIENTE';
    return {
      status: e.etapa === 'FALLIDO' ? 'error' : enCurso ? 'in-progress' : 'success',
      header: ETAPAS[e.etapa] ?? e.etapa,
      details: fechaHora(e.en),
    };
  });
  return <Steps steps={pasos} />;
}

function Perfil({ resultado }: { resultado: Resultado }) {
  const c = resultado.camposPersonalizados;
  return (
    <SpaceBetween size="l">
      <Container header={<Header variant="h2">Resumen del perfil</Header>}>
        <Box fontSize="heading-s">{texto(c.resumen_perfil)}</Box>
      </Container>
      {limpiarLista(c.logros_cuantificables).length > 0 && (
        <Container header={<Header variant="h2">Logros medibles</Header>}>
          <ul>
            {limpiarLista(c.logros_cuantificables).map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        </Container>
      )}
      <Container header={<Header variant="h2">Datos de contacto y perfil</Header>}>
        <KeyValuePairs
          columns={3}
          items={[
            { label: 'Correo', value: texto(c.email) },
            { label: 'Teléfono', value: texto(c.telefono) },
            { label: 'Ubicación', value: texto(c.ubicacion) },
            { label: 'LinkedIn', value: texto(c.linkedin) },
            { label: 'Otros enlaces', value: texto(limpiarLista(c.otros_enlaces)) },
            { label: 'Área profesional', value: texto(c.area_profesional) },
            { label: 'Idioma del documento', value: texto(c.idioma_documento) },
            {
              label: 'Idiomas estimados',
              info: 'BDA los infiere por el idioma del documento y la ubicación de la persona',
              value: (
                <SpaceBetween direction="horizontal" size="xs">
                  <Etiquetas valores={c.idiomas_estimados} />
                  {esBilingue(c.idiomas_estimados) && <Badge color="blue">Posible bilingüe</Badge>}
                </SpaceBetween>
              ),
            },
            { label: 'Seniority', value: texto(c.nivel_seniority) },
            { label: 'Años de experiencia', value: texto(c.anios_experiencia) },
            { label: 'Habilidades técnicas', value: <Etiquetas valores={c.habilidades_tecnicas} /> },
            { label: 'Habilidades blandas', value: <Etiquetas valores={c.habilidades_blandas} /> },
            { label: 'Certificaciones', value: <Etiquetas valores={c.certificaciones} /> },
          ]}
        />
      </Container>
      <TablaFilas
        titulo="Experiencia"
        filas={c.experiencia}
        columnas={['empresa', 'cargo', 'fecha_inicio', 'fecha_fin', 'logros_clave']}
      />
      <ColumnLayout columns={2}>
        <TablaFilas titulo="Educación" filas={c.educacion} columnas={['institucion', 'titulo', 'anio_fin']} />
        <TablaFilas titulo="Idiomas" filas={c.idiomas} columnas={['idioma', 'nivel']} />
      </ColumnLayout>
    </SpaceBetween>
  );
}

function SalidaEstandar({ resultado }: { resultado: Resultado }) {
  const s = resultado.salidaEstandar;
  const b = resultado.blueprintCoincidente;
  return (
    <Container header={<Header variant="h2">Salida estándar y clasificación</Header>}>
      <KeyValuePairs
        columns={4}
        items={[
          { label: 'Resumen del documento', value: texto(s.resumenDocumento) },
          { label: 'Páginas', value: texto(s.paginas) },
          { label: 'Blueprint aplicado', value: texto(b.nombre) },
          { label: 'Confianza de la clasificación', value: <Confianza valor={b.confianza} /> },
        ]}
      />
    </Container>
  );
}

const ALTO_PANEL = '75vh';

/** Figuras que BDA detectó y recortó del documento (fotos, logos, gráficos). */
function ImagenesExtraidas({ imagenes }: { imagenes: ImagenExtraida[] }) {
  if (!imagenes.length) {
    return <Box color="text-status-inactive">BDA no extrajo imágenes de este documento.</Box>;
  }
  return (
    <div style={{ maxHeight: ALTO_PANEL, overflow: 'auto' }}>
      <ColumnLayout columns={3} minColumnWidth={180}>
        {imagenes.map((img) => (
          <SpaceBetween key={img.url} size="xxs">
            <a href={img.url} target="_blank" rel="noreferrer">
              <img src={img.url} alt={img.descripcion || img.tipo} style={{ width: '100%', border: '1px solid #ddd', borderRadius: 4 }} />
            </a>
            <Box fontSize="body-s" color="text-body-secondary">
              {[img.tipo, img.pagina != null ? `página ${img.pagina + 1}` : ''].filter(Boolean).join(' · ')}
            </Box>
            {img.descripcion && <Box fontSize="body-s">{img.descripcion}</Box>}
          </SpaceBetween>
        ))}
      </ColumnLayout>
    </div>
  );
}

type VistaBda = 'tabla' | 'imagenes' | 'custom' | 'standard' | 'markdown';

function TablaHallazgos({ filas, aRevisar }: { filas: Hallazgo[]; aRevisar: string[] }) {
  const [expandidos, setExpandidos] = useState<Hallazgo[]>([]);
  return (
    <SpaceBetween size="m">
      {aRevisar.length > 0 && (
        <Alert type="warning" header="Campos para revisión humana">
          {aRevisar.map((c) => NOMBRES_CAMPO[c] ?? c).join(', ')}
        </Alert>
      )}
      <Table<Hallazgo>
        variant="embedded"
        items={filas}
        trackBy="id"
        wrapLines
        resizableColumns
        expandableRows={{
          getItemChildren: (f) => f.hijos ?? [],
          isItemExpandable: (f) => (f.hijos?.length ?? 0) > 0,
          expandedItems: expandidos,
          onExpandableItemToggle: ({ detail }) =>
            setExpandidos((actuales) =>
              detail.expanded ? [...actuales, detail.item] : actuales.filter((f) => f.id !== detail.item.id),
            ),
        }}
        empty={<Box color="text-status-inactive">BDA no devolvió campos para este documento</Box>}
        columnDefinitions={[
          { id: 'campo', header: 'Campo', minWidth: 200, cell: (f) => f.campo },
          { id: 'valor', header: 'Resultado', minWidth: 280, cell: (f) => f.valor || '-' },
          { id: 'confianza', header: 'Confianza', minWidth: 120, cell: (f) => <Confianza valor={f.confianza} /> },
          { id: 'pagina', header: 'Página', minWidth: 90, cell: (f) => f.pagina ?? '-' },
        ]}
      />
    </SpaceBetween>
  );
}

/** Resultados de BDA como en su consola: tabla de hallazgos o la respuesta tal cual (JSON o markdown). */
type Crudo = { standard: unknown; custom: unknown; imagenes: ImagenExtraida[] };

function ResultadosBda({
  resultado,
  datos,
  error,
  cargando,
}: {
  resultado: Resultado;
  datos: Crudo | null;
  error: string | null;
  cargando: boolean;
}) {
  const [vista, setVista] = useState<VistaBda>('tabla');

  let contenido;
  if (cargando) contenido = <Spinner size="large" />;
  else if (error) contenido = <Alert type="error">{error}</Alert>;
  else if (vista === 'imagenes') contenido = <ImagenesExtraidas imagenes={datos?.imagenes ?? []} />;
  else if (vista === 'tabla')
    contenido = <TablaHallazgos filas={hallazgosDesdeBda(datos?.custom)} aRevisar={resultado.camposARevisar ?? []} />;
  else {
    const crudo =
      vista === 'markdown'
        ? markdownDesdeBda(datos?.standard) || 'BDA no devolvió markdown para este documento.'
        : JSON.stringify(vista === 'custom' ? datos?.custom : datos?.standard, null, 2);
    contenido = (
      <div style={{ maxHeight: ALTO_PANEL, overflow: 'auto' }}>
        <CodeView lineNumbers wrapLines content={crudo} />
      </div>
    );
  }

  return (
    <Container
      header={
        <Header
          variant="h2"
          description="La confianza se muestra como nivel. El resumen y los logros medibles los redacta BDA: su confianza suele ser baja y no van a revisión."
          actions={
            <SegmentedControl
              selectedId={vista}
              onChange={({ detail }) => setVista(detail.selectedId as VistaBda)}
              options={[
                { id: 'tabla', text: 'Hallazgos' },
                { id: 'imagenes', text: `Imágenes (${datos?.imagenes.length ?? 0})` },
                { id: 'custom', text: 'JSON personalizado' },
                { id: 'standard', text: 'JSON estándar' },
                { id: 'markdown', text: 'Markdown' },
              ]}
            />
          }
        >
          Resultados de BDA
        </Header>
      }
    >
      {contenido}
    </Container>
  );
}

function DocumentoYHallazgos({ datos, documentoId }: { datos: DetalleDocumento; documentoId: string }) {
  const { seguimiento: s, resultado: r } = datos;
  return r ? (
    <ConResultados datos={datos} documentoId={documentoId} resultado={r} />
  ) : (
    <Grid gridDefinition={[{ colspan: { default: 12, l: 5 } }, { colspan: { default: 12, l: 7 } }]}>
      <Container header={<Header variant="h2" description={s.nombreOriginal}>Documento</Header>}>
        {datos.urlArchivo ? (
          <VisorDocumento key={documentoId} url={datos.urlArchivo} tipo={s.tipo} nombre={s.nombreOriginal} cajas={[]} />
        ) : (
          <Box color="text-status-inactive">Sin archivo</Box>
        )}
      </Container>
      <Container header={<Header variant="h2">Resultados de BDA</Header>}>
        <Box textAlign="center" padding="xl">
          {s.estado === 'PENDIENTE' ? (
            <>
              <Spinner size="large" /> <Box variant="p">Bedrock Data Automation está procesando el documento…</Box>
            </>
          ) : (
            'Este documento no tiene resultados de BDA.'
          )}
        </Box>
      </Container>
    </Grid>
  );
}

function ConResultados({
  datos,
  documentoId,
  resultado,
}: {
  datos: DetalleDocumento;
  documentoId: string;
  resultado: Resultado;
}) {
  const s = datos.seguimiento;
  const [verCajas, setVerCajas] = useState(true);
  const crudo = useSondeo(() => obtenerCrudo(documentoId), () => false);
  const cajas = verCajas ? cajasDesdeBda(crudo.datos?.custom) : [];
  return (
    <Grid gridDefinition={[{ colspan: { default: 12, l: 5 } }, { colspan: { default: 12, l: 7 } }]}>
      <Container
        header={
          <Header
            variant="h2"
            description={s.nombreOriginal}
            actions={
              <SpaceBetween direction="horizontal" size="m" alignItems="center">
                <Toggle
                  checked={verCajas}
                  onChange={({ detail }: { detail: ToggleProps.ChangeDetail }) => setVerCajas(detail.checked)}
                >
                  Mostrar cajas
                </Toggle>
                {datos.urlDescarga && (
                  <Button iconName="download" href={datos.urlDescarga}>
                    Descargar
                  </Button>
                )}
              </SpaceBetween>
            }
          >
            Documento
          </Header>
        }
      >
        {datos.urlArchivo ? (
          <VisorDocumento key={documentoId} url={datos.urlArchivo} tipo={s.tipo} nombre={s.nombreOriginal} cajas={cajas} />
        ) : (
          <Box color="text-status-inactive">Sin archivo</Box>
        )}
      </Container>
      <ResultadosBda resultado={resultado} datos={crudo.datos} error={crudo.error} cargando={crudo.cargando} />
    </Grid>
  );
}

export default function Detalle() {
  const { id = '' } = useParams();
  const config = useConfig();
  const [pestana, setPestana] = useState('hallazgos');
  const { datos, error } = useSondeo<DetalleDocumento>(
    () => obtenerDocumento(id),
    (d) => d.seguimiento.estado === 'PENDIENTE',
  );

  if (error) return <Alert type="error" header="No pudimos cargar el análisis">{error}</Alert>;
  if (!datos) return <Spinner size="large" />;
  const { seguimiento: s, resultado: r } = datos;

  return (
    <ContentLayout
      header={
        <Header variant="h1" description={s.nombreOriginal} info={<EstadoDocumento estado={s.estado} />}>
          {r?.camposPersonalizados.nombre_completo || s.nombreOriginal}
          {r?.camposPersonalizados.titulo_profesional ? ` · ${r.camposPersonalizados.titulo_profesional}` : ''}
        </Header>
      }
    >
      <SpaceBetween size="l">
        {s.estado === 'FALLIDO' && (
          <Alert type="error" header="El procesamiento falló">
            {s.motivo || 'Sin detalle'}
          </Alert>
        )}
        <ColumnLayout columns={2}>
          <Container header={<Header variant="h2">Línea de tiempo</Header>}>
            <LineaDeTiempo seguimiento={s} />
          </Container>
          <Container header={<Header variant="h2">Procesamiento</Header>}>
            <KeyValuePairs
              columns={2}
              items={[
                { label: 'Subido por', value: texto(s.email) },
                { label: 'Subido', value: fechaHora(s.creadoEn) },
                { label: 'Páginas', value: texto(s.paginas) },
                { label: 'Costo estimado', value: usd(s.costoEstimadoUsd) },
                { label: 'Segundos totales', value: texto(s.segundosTotales) },
                { label: 'Consultas de estado a BDA', value: texto(s.vueltasSondeo) },
                {
                  label: 'Entrada en S3',
                  value: s.s3Key ? (
                    <Link
                      external
                      href={`https://s3.console.aws.amazon.com/s3/object/${config.bucketCvs}?region=${config.region}&prefix=${encodeURIComponent(s.s3Key)}`}
                    >
                      {s.s3Key}
                    </Link>
                  ) : (
                    '-'
                  ),
                },
                {
                  label: 'Salida de BDA en S3',
                  value: (
                    <Link
                      external
                      href={`https://s3.console.aws.amazon.com/s3/buckets/${config.bucketResultadosBda}?region=${config.region}&prefix=${encodeURIComponent(`bda/${s.documentoId}/`)}`}
                    >
                      {`bda/${s.documentoId}/`}
                    </Link>
                  ),
                },
                {
                  label: 'Ejecución de Step Functions',
                  value: s.ejecucionArn ? (
                    <Link external href={`${config.consolaStepFunctions}${s.ejecucionArn}`}>
                      Abrir en la consola
                    </Link>
                  ) : (
                    '-'
                  ),
                },
              ]}
            />
          </Container>
        </ColumnLayout>
        <Tabs
          activeTabId={pestana}
          onChange={({ detail }) => setPestana(detail.activeTabId)}
          tabs={[
            {
              id: 'hallazgos',
              label: 'Documento y hallazgos',
              content: <DocumentoYHallazgos datos={datos} documentoId={id} />,
            },
            {
              id: 'perfil',
              label: 'Perfil',
              disabled: !r,
              content: r && (
                <SpaceBetween size="l">
                  <Perfil resultado={r} />
                  <SalidaEstandar resultado={r} />
                </SpaceBetween>
              ),
            },
          ]}
        />
      </SpaceBetween>
    </ContentLayout>
  );
}
