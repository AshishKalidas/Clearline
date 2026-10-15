import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import type { Credentials } from '../types';

export type Appearance = 'system' | 'light' | 'dark';
const defaults: Credentials = { reviewer: 'Demo Reviewer', apiKey: 'clearline-local-demo' };
function readCredentials(): Credentials {
  try {
    const value: unknown = JSON.parse(sessionStorage.getItem('clearline-reviewer') ?? 'null');
    if (
      value &&
      typeof value === 'object' &&
      'reviewer' in value &&
      'apiKey' in value &&
      typeof value.reviewer === 'string' &&
      typeof value.apiKey === 'string'
    )
      return { reviewer: value.reviewer, apiKey: value.apiKey };
  } catch {
    /* Unavailable storage should not prevent access to the workspace. */
  }
  return defaults;
}
function readAppearance(): Appearance {
  try {
    const value = localStorage.getItem('clearline-appearance');
    if (value === 'light' || value === 'dark') return value;
  } catch {
    /* Use the system preference when storage is unavailable. */
  }
  return 'system';
}
/** Apply the saved theme before React creates any controls, avoiding a light-theme flash. */
export function restoreAppearance() {
  document.documentElement.dataset.theme = readAppearance();
}
interface Preferences {
  credentials: Credentials;
  saveCredentials: (value: Credentials) => void;
  appearance: Appearance;
  setAppearance: (value: Appearance) => void;
}
const Context = createContext<Preferences | null>(null);
export function PreferencesProvider({ children }: { children: ReactNode }) {
  const [credentials, setCredentials] = useState(readCredentials);
  const [appearance, setAppearance] = useState(readAppearance);
  useEffect(() => {
    document.documentElement.dataset.theme = appearance;
    try {
      localStorage.setItem('clearline-appearance', appearance);
    } catch {
      /* Optional persistence. */
    }
  }, [appearance]);
  function saveCredentials(value: Credentials) {
    setCredentials(value);
    try {
      sessionStorage.setItem('clearline-reviewer', JSON.stringify(value));
    } catch {
      /* Optional persistence. */
    }
  }
  return (
    <Context.Provider value={{ credentials, saveCredentials, appearance, setAppearance }}>
      {children}
    </Context.Provider>
  );
}
export function usePreferences() {
  const preferences = useContext(Context);
  if (!preferences) throw new Error('Preferences must be provided.');
  return preferences;
}
