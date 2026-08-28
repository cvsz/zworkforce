import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export function Markdown({ children }: { children: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        a: ({ children: linkText, ...props }) => (
          <a {...props} target="_blank" rel="noreferrer">
            {linkText}
          </a>
        ),
        code: ({ children: code }) => <code>{code}</code>,
      }}
    >
      {children}
    </ReactMarkdown>
  );
}
