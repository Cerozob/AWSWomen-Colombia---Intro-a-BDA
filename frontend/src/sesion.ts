import { fetchAuthSession, signInWithRedirect, signOut } from 'aws-amplify/auth';

export interface Sesion {
  correo: string;
  reclutamiento: boolean;
}

/** Lee la sesión que dejó el login administrado de Cognito (null si no hay sesión). */
export async function leerSesion(): Promise<Sesion | null> {
  const { tokens } = await fetchAuthSession();
  const reclamos = tokens?.idToken?.payload;
  if (!reclamos) return null;
  const grupos = (reclamos['cognito:groups'] as string[] | undefined) ?? [];
  return { correo: String(reclamos.email ?? ''), reclutamiento: grupos.includes('reclutamiento') };
}

/** Lleva a las pantallas de Cognito (inicio de sesión y registro), en español. */
export const iniciarSesion = () => signInWithRedirect({ options: { lang: 'es' } });

export const cerrarSesion = () => signOut();
