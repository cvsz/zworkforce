export default function Loading() {
  return (
    <div
      style={{
        maxWidth: '1280px',
        margin: '0 auto',
        padding: '80px 24px 40px',
      }}
    >
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '16px',
          marginBottom: '28px',
        }}
      >
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="shimmer"
            style={{ height: '100px', borderRadius: 'var(--radius-lg)' }}
          />
        ))}
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '28px',
          marginBottom: '32px',
        }}
      >
        <div className="shimmer" style={{ height: '340px', borderRadius: 'var(--radius-lg)' }} />
        <div className="shimmer" style={{ height: '400px', borderRadius: 'var(--radius-lg)' }} />
      </div>

      <div className="shimmer" style={{ height: '260px', borderRadius: 'var(--radius-lg)' }} />
    </div>
  );
}
