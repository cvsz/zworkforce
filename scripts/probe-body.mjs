export function withJsonBody(headers, body) {
  if (body === undefined) return { headers, body: undefined };
  return {
    headers: { ...headers, "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}
