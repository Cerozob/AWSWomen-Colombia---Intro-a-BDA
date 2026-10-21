import AppLayout from '@cloudscape-design/components/app-layout';
import Box from '@cloudscape-design/components/box';
import Button from '@cloudscape-design/components/button';
import Container from '@cloudscape-design/components/container';
import Header from '@cloudscape-design/components/header';
import SideNavigation, { type SideNavigationProps } from '@cloudscape-design/components/side-navigation';
import SpaceBetween from '@cloudscape-design/components/space-between';
import Spinner from '@cloudscape-design/components/spinner';
import TopNavigation from '@cloudscape-design/components/top-navigation';
import { useEffect, useState } from 'react';
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router';
import Analisis from './paginas/Analisis';
import Detalle from './paginas/Detalle';
import Subir from './paginas/Subir';
import { cerrarSesion, iniciarSesion, leerSesion, type Sesion } from './sesion';

function Aplicacion({ sesion }: { sesion: Sesion }) {
  const navegar = useNavigate();
  const { pathname } = useLocation();
  const activo = ['/todas', '/hojas-de-vida', '/subir'].find((r) => pathname.startsWith(r)) ?? '/subir';

  const enlaces: SideNavigationProps.Item[] = [
    { type: 'link', text: 'Subir hojas de vida', href: '/subir' },
    { type: 'link', text: 'Mis hojas de vida', href: '/hojas-de-vida' },
  ];
  if (sesion.reclutamiento) {
    enlaces.push(
      { type: 'divider' },
      { type: 'section-group', title: 'Equipo de reclutamiento', items: [{ type: 'link', text: 'Todas las candidaturas', href: '/todas' }] },
    );
  }

  return (
    <>
      <div id="barra-superior" style={{ position: 'sticky', top: 0, zIndex: 1002 }}>
        <TopNavigation
          identity={{
            href: '/',
            title: 'ATS con Bedrock Data Automation',
            onFollow: (e) => {
              e.preventDefault();
              navegar('/');
            },
          }}
          utilities={[
            {
              type: 'menu-dropdown',
              text: sesion.correo,
              description: sesion.reclutamiento ? 'Equipo de reclutamiento' : 'Persona candidata',
              iconName: 'user-profile',
              items: [{ id: 'salir', text: 'Cerrar sesión' }],
              onItemClick: ({ detail }) => {
                if (detail.id === 'salir') cerrarSesion();
              },
            },
          ]}
        />
      </div>
      <AppLayout
        headerSelector="#barra-superior"
        toolsHide
        // Ocupa todo el ancho (pantallas 1080p): tablas anchas y el visor al lado de los hallazgos.
        maxContentWidth={Number.MAX_VALUE}
        navigation={
          <SideNavigation
            activeHref={activo}
            header={{ href: '/', text: 'Demo AWS Women Colombia' }}
            onFollow={(e) => {
              e.preventDefault();
              navegar(e.detail.href);
            }}
            items={enlaces}
          />
        }
        content={
          <Routes>
            <Route path="/subir" element={<Subir />} />
            <Route path="/hojas-de-vida" element={<Analisis key="mias" vista="mias" />} />
            <Route path="/hojas-de-vida/:id" element={<Detalle />} />
            <Route
              path="/todas"
              element={sesion.reclutamiento ? <Analisis key="todas" vista="todas" /> : <Navigate to="/hojas-de-vida" replace />}
            />
            <Route path="*" element={<Navigate to="/subir" replace />} />
          </Routes>
        }
      />
    </>
  );
}

/** Sin sesión: botón que lleva al login administrado de Cognito (la app no dibuja formularios de login). */
function Bienvenida() {
  return (
    <Box padding="xxxl">
      <Container
        header={
          <Header variant="h1" description="Demo de Amazon Bedrock Data Automation · AWS Women Colombia">
            ATS de hojas de vida
          </Header>
        }
      >
        <SpaceBetween size="l">
          <Box variant="p">Inicia sesión o crea tu cuenta para subir hojas de vida y ver su análisis.</Box>
          <Button variant="primary" onClick={() => iniciarSesion()}>
            Iniciar sesión o registrarse
          </Button>
        </SpaceBetween>
      </Container>
    </Box>
  );
}

export default function App() {
  const [sesion, setSesion] = useState<Sesion | null | undefined>(undefined);

  useEffect(() => {
    // Al volver del login administrado, Amplify cambia el código por los tokens antes de responder.
    leerSesion()
      .then(setSesion)
      .catch(() => setSesion(null));
  }, []);

  if (sesion === undefined) return <Box padding="xxxl" textAlign="center"><Spinner size="large" /></Box>;
  return sesion ? <Aplicacion sesion={sesion} /> : <Bienvenida />;
}
