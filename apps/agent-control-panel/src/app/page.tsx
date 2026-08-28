'use client';
import { useState } from 'react';

const PROVIDERS = [
  'groq', 'huggingface', 'openrouter', 'mistral', 'together', 
  'cerebras', 'sambanova', 'gemini', 'deepseek', 'fireworks',
  'cohere', 'anthropic', 'openai', 'perplexity', 'replicate',
  'ai21', 'anyscale', 'cloudflare', 'databricks', 'voyage'
];

export default function ControlPanel() {
  const [selectedProvider, setSelectedProvider] = useState('groq');
  const [apiKey, setApiKey] = useState('');
  const [status, setStatus] = useState('');

  const handleAddKey = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatus('Saving...');
    // In a real app, this posts to the AI Gateway or billing service to store in Redis
    setTimeout(() => {
      setStatus(`Key saved for ${selectedProvider} and added to rotation pool.`);
      setApiKey('');
    }, 500);
  };

  return (
    <main className="min-h-screen p-8 bg-[#0a0a0a] text-white">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-4xl font-bold mb-2">AI Agents Control Panel</h1>
        <p className="text-gray-400 mb-8">Manage API key pools and auto-rotation for 20 free providers.</p>

        <div className="bg-[#141414] border border-gray-800 rounded-xl p-6">
          <h2 className="text-xl font-semibold mb-4">Add API Key to Rotation Pool</h2>
          <form onSubmit={handleAddKey} className="space-y-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Select Provider</label>
              <select 
                className="w-full bg-black border border-gray-800 rounded-lg p-3 text-white focus:outline-none focus:border-blue-500"
                value={selectedProvider}
                onChange={(e) => setSelectedProvider(e.target.value)}
              >
                {PROVIDERS.map(p => (
                  <option key={p} value={p}>{p.toUpperCase()}</option>
                ))}
              </select>
            </div>
            
            <div>
              <label className="block text-sm text-gray-400 mb-1">API Key</label>
              <input 
                type="password" 
                placeholder="sk-..."
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                className="w-full bg-black border border-gray-800 rounded-lg p-3 text-white focus:outline-none focus:border-blue-500"
                required
              />
            </div>
            
            <button 
              type="submit"
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-4 rounded-lg transition-colors"
            >
              Add Key
            </button>
            {status && <p className="text-green-400 text-sm mt-2">{status}</p>}
          </form>
        </div>
      </div>
    </main>
  );
}
