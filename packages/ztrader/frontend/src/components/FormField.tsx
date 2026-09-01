"use client";

import React from 'react';

interface FormFieldProps {
  label: string;
  error?: string | null;
  hint?: string;
  children: React.ReactNode;
  htmlFor?: string;
}

export function FormField({ label, error, hint, children, htmlFor }: FormFieldProps) {
  const id = htmlFor || (React.isValidElement(children) ? (children as React.ReactElement<{ id?: string }>).props.id : undefined);
  const errorId = id ? `${id}-error` : undefined;
  const hintId = id ? `${id}-hint` : undefined;
  const describedBy = [error ? errorId : undefined, hint ? hintId : undefined].filter(Boolean).join(' ') || undefined;

  return (
    <div className="form-group" role="group" aria-labelledby={id ? `${id}-label` : undefined}>
      <label
        id={id ? `${id}-label` : undefined}
        className="form-label"
        htmlFor={id}
      >
        {label}
      </label>
      {React.cloneElement(children as React.ReactElement, {
        ...(id ? { 'aria-describedby': describedBy, 'aria-invalid': !!error || undefined } : {}),
      })}
      {hint && (
        <small
          id={hintId}
          className="text-muted"
          style={{ fontSize: '11px', display: 'block', marginTop: '4px' }}
        >
          {hint}
        </small>
      )}
      {error && (
        <span
          id={errorId}
          role="alert"
          style={{
            display: 'block',
            fontSize: '12px',
            color: 'var(--color-danger)',
            marginTop: '4px',
          }}
        >
          {error}
        </span>
      )}
    </div>
  );
}
