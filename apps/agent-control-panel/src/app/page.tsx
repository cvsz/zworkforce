export default function ControlPanel() {
  return (
    <main className="min-h-screen p-8 bg-[#0a0a0a] text-white">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-4xl font-bold mb-2">ZEAZ Center Control Plane</h1>
        <p className="text-gray-400 mb-8">
          Operator dashboard foundation. No provider credentials are accepted or stored in this browser.
        </p>

        <div className="bg-[#141414] border border-gray-800 rounded-xl p-6" aria-labelledby="inventory-heading">
          <h2 id="inventory-heading" className="text-xl font-semibold mb-3">Fleet inventory</h2>
          <p className="text-gray-300">Live GitHub and Cloudflare inventory is not connected yet.</p>
          <p className="text-gray-500 mt-2">
            The current implementation provides the Phase 0 contract only. No external state or production readiness is being reported.
          </p>
        </div>
      </div>
    </main>
  );
}
