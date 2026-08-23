import type { ReactNode } from "react";

type IconProps = Readonly<{ className?: string }>;

function Icon({ children, className }: Readonly<IconProps & { children: ReactNode }>) {
  return (
    <svg aria-hidden="true" viewBox="0 0 20 20" className={`icon${className ? ` ${className}` : ""}`}>
      {children}
    </svg>
  );
}

export function ArrowIcon({ className }: IconProps) {
  return (
    <Icon className={`icon-arrow${className ? ` ${className}` : ""}`}>
      <path d="M4 10h11" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.7" />
      <path d="m10.5 4.5 5.5 5.5-5.5 5.5" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.7" />
    </Icon>
  );
}

export function CheckIcon({ className }: IconProps) {
  return (
    <Icon className={className}>
      <path d="m4.5 10.5 3.3 3.3 7.7-7.7" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" />
    </Icon>
  );
}

export function TerminalIcon({ className }: IconProps) {
  return (
    <Icon className={className}>
      <path d="m4.5 6.5 3.5 3.5-3.5 3.5M10.5 13.5h5" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.6" />
    </Icon>
  );
}

export function ShieldIcon({ className }: IconProps) {
  return (
    <Icon className={className}>
      <path d="M10 2.5 15.5 4.7v4.2c0 3.9-2.5 6.9-5.5 8.6-3-1.7-5.5-4.7-5.5-8.6V4.7L10 2.5z" fill="none" stroke="currentColor" strokeLinejoin="round" strokeWidth="1.5" />
      <path d="m7.2 10 1.8 1.8 3.8-4" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" />
    </Icon>
  );
}

export function RouteIcon({ className }: IconProps) {
  return (
    <Icon className={className}>
      <circle cx="5" cy="5" r="2" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="15" cy="15" r="2" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <path d="M6.8 6.4c1.4 1.1 1.8 2.5 1.8 3.6s.4 2.5 1.8 3.6" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.5" />
    </Icon>
  );
}

export function StackIcon({ className }: IconProps) {
  return (
    <Icon className={className}>
      <path d="m10 3 6.5 3.3L10 9.6 3.5 6.3 10 3z" fill="none" stroke="currentColor" strokeLinejoin="round" strokeWidth="1.5" />
      <path d="m3.5 10 6.5 3.3 6.5-3.3M3.5 13.7l6.5 3.3 6.5-3.3" fill="none" stroke="currentColor" strokeLinejoin="round" strokeWidth="1.5" />
    </Icon>
  );
}

export function MenuIcon({ className }: IconProps) {
  return (
    <Icon className={className}>
      <path d="M3.5 5.5h13M3.5 10h13M3.5 14.5h13" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.5" />
    </Icon>
  );
}

export function GlobeIcon({ className }: IconProps) {
  return (
    <Icon className={className}>
      <circle cx="10" cy="10" r="6.8" fill="none" stroke="currentColor" strokeWidth="1.4" />
      <path d="M3.5 10h13M10 3.2c1.7 1.8 2.5 4.1 2.5 6.8S11.7 15 10 16.8C8.3 15 7.5 12.7 7.5 10S8.3 5 10 3.2z" fill="none" stroke="currentColor" strokeWidth="1.2" />
    </Icon>
  );
}

export function CopyIcon({ className }: IconProps) {
  return (
    <Icon className={className}>
      <rect x="7" y="7" width="9" height="9" rx="1.5" fill="none" stroke="currentColor" strokeWidth="1.4" />
      <path d="M5.5 13H4.5A1.5 1.5 0 0 1 3 11.5v-7A1.5 1.5 0 0 1 4.5 3h7A1.5 1.5 0 0 1 13 4.5v1" fill="none" stroke="currentColor" strokeWidth="1.4" />
    </Icon>
  );
}

