/** Public static deployments expose only the isolated, browser-owned sample workspace. */
export function isDemoDeployment(): boolean {
  return import.meta.env.MODE === 'demo';
}
