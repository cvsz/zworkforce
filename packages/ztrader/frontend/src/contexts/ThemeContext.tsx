"use client";

import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';

type Theme = 'light' | 'dark' | 'auto';

interface ThemeContextType {
  theme: Theme;
  actualTheme: 'light' | 'dark';
  setTheme: (theme: Theme) => void;
  primaryColor: string;
  secondaryColor: string;
  accentColor: string;
  setPrimaryColor: (color: string) => void;
  setSecondaryColor: (color: string) => void;
  setAccentColor: (color: string) => void;
  reducedMotion: boolean;
  setReducedMotion: (value: boolean) => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

const STORAGE_KEYS = {
  theme: 'ztrader_theme',
  primaryColor: 'ztrader_primary_color',
  secondaryColor: 'ztrader_secondary_color',
  accentColor: 'ztrader_accent_color',
  reducedMotion: 'ztrader_reduced_motion',
} as const;

const DEFAULT_COLORS = {
  primary: '#3B82F6',
  secondary: '#8B5CF6',
  accent: '#10B981',
} as const;

function getSystemTheme(): 'light' | 'dark' {
  if (typeof window !== 'undefined') {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  return 'dark';
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<Theme>('dark');
  const [actualTheme, setActualTheme] = useState<'light' | 'dark'>('dark');
  const [primaryColor, setPrimaryColorState] = useState<string>(DEFAULT_COLORS.primary);
  const [secondaryColor, setSecondaryColorState] = useState<string>(DEFAULT_COLORS.secondary);
  const [accentColor, setAccentColorState] = useState<string>(DEFAULT_COLORS.accent);
  const [reducedMotion, setReducedMotionState] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    if (typeof window === 'undefined') return;

    const savedTheme = localStorage.getItem(STORAGE_KEYS.theme) as Theme;
    const savedPrimary = localStorage.getItem(STORAGE_KEYS.primaryColor);
    const savedSecondary = localStorage.getItem(STORAGE_KEYS.secondaryColor);
    const savedAccent = localStorage.getItem(STORAGE_KEYS.accentColor);
    const savedReducedMotion = localStorage.getItem(STORAGE_KEYS.reducedMotion);

    if (savedTheme) setThemeState(savedTheme);
    if (savedPrimary) setPrimaryColorState(savedPrimary);
    if (savedSecondary) setSecondaryColorState(savedSecondary);
    if (savedAccent) setAccentColorState(savedAccent);
    if (savedReducedMotion) setReducedMotionState(savedReducedMotion === 'true');
  }, []);

  const applyTheme = useCallback(() => {
    if (typeof document === 'undefined') return;

    const resolved = theme === 'auto' ? getSystemTheme() : theme;
    setActualTheme(resolved);

    document.documentElement.classList.remove('light', 'dark');
    document.documentElement.classList.add(resolved);

    const root = document.documentElement;
    root.style.setProperty('--color-primary', primaryColor);
    root.style.setProperty('--color-secondary', secondaryColor);
    root.style.setProperty('--color-accent', accentColor);

    if (reducedMotion) {
      root.style.setProperty('--transition-smooth', 'all 0.1s linear');
      root.style.setProperty('--transition-spring', 'all 0.1s linear');
    } else {
      root.style.setProperty('--transition-smooth', 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)');
      root.style.setProperty('--transition-spring', 'all 0.5s cubic-bezier(0.34, 1.56, 0.64, 1)');
    }
  }, [theme, primaryColor, secondaryColor, accentColor, reducedMotion]);

  useEffect(() => {
    applyTheme();
  }, [applyTheme]);

  useEffect(() => {
    if (theme !== 'auto') return;
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = () => applyTheme();
    mediaQuery.addEventListener('change', handler);
    return () => mediaQuery.removeEventListener('change', handler);
  }, [theme, applyTheme]);

  const setTheme = useCallback((newTheme: Theme) => {
    setThemeState(newTheme);
    if (typeof window !== 'undefined') {
      localStorage.setItem(STORAGE_KEYS.theme, newTheme);
    }
  }, []);

  const setPrimaryColor = useCallback((color: string) => {
    setPrimaryColorState(color);
    if (typeof window !== 'undefined') {
      localStorage.setItem(STORAGE_KEYS.primaryColor, color);
    }
  }, []);

  const setSecondaryColor = useCallback((color: string) => {
    setSecondaryColorState(color);
    if (typeof window !== 'undefined') {
      localStorage.setItem(STORAGE_KEYS.secondaryColor, color);
    }
  }, []);

  const setAccentColor = useCallback((color: string) => {
    setAccentColorState(color);
    if (typeof window !== 'undefined') {
      localStorage.setItem(STORAGE_KEYS.accentColor, color);
    }
  }, []);

  const setReducedMotion = useCallback((value: boolean) => {
    setReducedMotionState(value);
    if (typeof window !== 'undefined') {
      localStorage.setItem(STORAGE_KEYS.reducedMotion, String(value));
    }
  }, []);

  const contextValue = {
    theme,
    actualTheme,
    setTheme,
    primaryColor,
    secondaryColor,
    accentColor,
    setPrimaryColor,
    setSecondaryColor,
    setAccentColor,
    reducedMotion,
    setReducedMotion,
  };

  if (!mounted && typeof window === 'undefined') {
    return <div style={{ visibility: 'hidden' }}>{children}</div>;
  }

  return (
    <ThemeContext.Provider value={contextValue}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
}
