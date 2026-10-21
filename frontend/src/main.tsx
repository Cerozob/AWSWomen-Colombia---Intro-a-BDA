import '@cloudscape-design/global-styles/index.css';
// Procesa el regreso del login administrado de Cognito (code + PKCE) en esta SPA.
import 'aws-amplify/auth/enable-oauth-listener';

import { I18nProvider } from '@cloudscape-design/components/i18n';
import mensajesEs from '@cloudscape-design/components/i18n/messages/all.es';
import { Amplify } from 'aws-amplify';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router';
import { configurarApi } from './api';
import App from './App';
import { ConfigContexto } from './componentes';
import type { ConfigWeb } from './tipos';

// config.json lo genera el CDK al desplegar, con las direcciones reales del stack.
async function iniciar() {
  const raiz = createRoot(document.getElementById('root')!);
  const respuesta = await fetch('/config.json');
  if (!respuesta.ok) {
    raiz.render(<p>Falta config.json. Despliega el stack con CDK.</p>);
    return;
  }
  const config: ConfigWeb = await respuesta.json();
  const retorno = `${config.urlSitio}/`;
  Amplify.configure({
    Auth: {
      Cognito: {
        userPoolId: config.userPoolId,
        userPoolClientId: config.userPoolClientId,
        loginWith: {
          oauth: {
            domain: config.dominioLogin,
            scopes: ['openid', 'email', 'profile'],
            redirectSignIn: [retorno],
            redirectSignOut: [retorno],
            responseType: 'code',
          },
        },
      },
    },
  });
  configurarApi(config.apiUrl);

  raiz.render(
    <StrictMode>
      <I18nProvider locale="es" messages={[mensajesEs]}>
        <ConfigContexto.Provider value={config}>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </ConfigContexto.Provider>
      </I18nProvider>
    </StrictMode>,
  );
}

iniciar();
