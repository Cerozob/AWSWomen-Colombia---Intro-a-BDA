import Badge from '@cloudscape-design/components/badge';
import StatusIndicator from '@cloudscape-design/components/status-indicator';
import { createContext, useContext } from 'react';
import { COLOR_NIVEL, ESTADOS, nivelConfianza } from './formato';
import type { ConfigWeb, Estado } from './tipos';

export const ConfigContexto = createContext<ConfigWeb | null>(null);

export function useConfig(): ConfigWeb {
  const config = useContext(ConfigContexto);
  if (!config) throw new Error('Falta ConfigContexto');
  return config;
}

export function EstadoDocumento({ estado }: { estado: Estado }) {
  const { texto, tipo } = ESTADOS[estado] ?? { texto: estado, tipo: 'info' };
  return <StatusIndicator type={tipo}>{texto}</StatusIndicator>;
}

export function Confianza({ valor }: { valor?: number | null }) {
  const { confianza } = useConfig();
  if (valor == null) return <>-</>;
  const nivel = nivelConfianza(valor, confianza);
  return <Badge color={COLOR_NIVEL[nivel]}>{nivel}</Badge>;
}
