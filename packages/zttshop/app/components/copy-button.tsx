"use client";

import { useState } from "react";
import { CheckIcon, CopyIcon } from "@/app/components/icons";

type CopyButtonProps = Readonly<{
  text: string;
  copyLabel?: string;
  copiedLabel?: string;
  className?: string;
}>;

export function CopyButton({
  text,
  copyLabel = "Copy",
  copiedLabel = "Copied!",
  className = "copy-button",
}: CopyButtonProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      if (typeof navigator !== "undefined" && navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        throw new Error("Clipboard API unavailable");
      }
    } catch {
      const textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button
      type="button"
      className={`${className}${copied ? " copied" : ""}`}
      onClick={handleCopy}
      aria-label={copied ? copiedLabel : copyLabel}
    >
      {copied ? <CheckIcon className="icon icon-copied" /> : <CopyIcon className="icon icon-copy" />}
      <span>{copied ? copiedLabel : copyLabel}</span>
    </button>
  );
}
