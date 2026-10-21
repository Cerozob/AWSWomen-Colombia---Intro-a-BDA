import Box from '@cloudscape-design/components/box';
import Button from '@cloudscape-design/components/button';
import Container from '@cloudscape-design/components/container';
import ContentLayout from '@cloudscape-design/components/content-layout';
import FileUpload, { type FileUploadProps } from '@cloudscape-design/components/file-upload';
import Flashbar, { type FlashbarProps } from '@cloudscape-design/components/flashbar';
import FormField from '@cloudscape-design/components/form-field';
import Header from '@cloudscape-design/components/header';
import Link from '@cloudscape-design/components/link';
import SpaceBetween from '@cloudscape-design/components/space-between';
import { useState } from 'react';
import { useNavigate } from 'react-router';
import { subirHojaDeVida } from '../api';

// Extensiones y tipos MIME: algunos selectores de archivos (p. ej. la galería del celular) filtran por tipo.
const FORMATOS = '.pdf,.docx,.jpg,.jpeg,.png,.tif,.tiff,application/pdf,image/jpeg,image/png,image/tiff';

export default function Subir() {
  const navegar = useNavigate();
  const [archivos, setArchivos] = useState<File[]>([]);
  const [subiendo, setSubiendo] = useState(false);
  const [avisos, setAvisos] = useState<FlashbarProps.MessageDefinition[]>([]);

  async function analizar() {
    setSubiendo(true);
    // Todos a la vez: así el tiempo de BDA corre en paralelo mientras se explica el flujo.
    const resultados = await Promise.allSettled(archivos.map((a) => subirHojaDeVida(a)));
    const nuevos: FlashbarProps.MessageDefinition[] = resultados.map((r, i) => {
      const nombre = archivos[i].name;
      if (r.status === 'fulfilled') {
        return {
          id: r.value,
          type: 'success',
          dismissible: true,
          content: (
            <>
              {nombre}: subido. <Link onFollow={() => navegar(`/hojas-de-vida/${r.value}`)}>Ver el análisis</Link>
            </>
          ),
          onDismiss: () => setAvisos((a) => a.filter((x) => x.id !== r.value)),
        };
      }
      return {
        id: `error-${i}`,
        type: 'error',
        dismissible: true,
        content: `${nombre}: ${r.reason instanceof Error ? r.reason.message : String(r.reason)}`,
        onDismiss: () => setAvisos((a) => a.filter((x) => x.id !== `error-${i}`)),
      };
    });
    setAvisos(nuevos);
    setArchivos([]);
    setSubiendo(false);
  }

  return (
    <ContentLayout
      header={
        <Header variant="h1" description="Sube una o varias hojas de vida. Bedrock Data Automation las convierte en un perfil estructurado.">
          Subir hojas de vida
        </Header>
      }
    >
      <SpaceBetween size="l">
        <Flashbar items={avisos} />
        <Container>
          <SpaceBetween size="l">
            <FormField
              label="Archivos"
              description="Puedes arrastrarlos y soltarlos aquí."
              constraintText="Formatos: PDF, DOCX, JPG, PNG o TIFF; también fotos de una hoja de vida impresa."
            >
              <FileUpload
                multiple
                accept={FORMATOS}
                value={archivos}
                onChange={({ detail }: { detail: FileUploadProps.ChangeDetail }) => setArchivos(detail.value)}
                showFileSize
                tokenLimit={5}
              />
            </FormField>
            <Box float="right">
              <Button variant="primary" loading={subiendo} disabled={!archivos.length} onClick={analizar}>
                Analizar {archivos.length > 1 ? `${archivos.length} archivos` : ''}
              </Button>
            </Box>
          </SpaceBetween>
        </Container>
      </SpaceBetween>
    </ContentLayout>
  );
}
