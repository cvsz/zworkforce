import { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Analytics Dashboard',
  description: 'z-platform MetricUI Analytics Dashboard',
}

export default function AnalyticsPage() {
  return (
    <div className="min-h-screen bg-background">
      <header className="border-b">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <h1 className="text-2xl font-bold">Analytics Dashboard</h1>
          <span className="text-sm text-muted-foreground">
            Powered by MetricUI
          </span>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div className="rounded-xl border bg-card p-6 shadow">
            <div className="text-sm font-medium text-muted-foreground">Total Revenue</div>
            <div className="text-3xl font-bold mt-2">$45,231</div>
            <div className="text-xs text-green-600 mt-1">+20.1% from last month</div>
          </div>
          <div className="rounded-xl border bg-card p-6 shadow">
            <div className="text-sm font-medium text-muted-foreground">Active Users</div>
            <div className="text-3xl font-bold mt-2">12,345</div>
            <div className="text-xs text-green-600 mt-1">+15.3% from last month</div>
          </div>
          <div className="rounded-xl border bg-card p-6 shadow">
            <div className="text-sm font-medium text-muted-foreground">Bounce Rate</div>
            <div className="text-3xl font-bold mt-2">42.3%</div>
            <div className="text-xs text-red-600 mt-1">-2.1% from last week</div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="rounded-xl border bg-card p-6 shadow">
            <h2 className="text-lg font-semibold mb-4">Revenue Overview</h2>
            <div className="h-[300px] flex items-center justify-center border-2 border-dashed rounded-lg">
              <p className="text-muted-foreground">MetricUI chart placeholder</p>
            </div>
          </div>

          <div className="rounded-xl border bg-card p-6 shadow">
            <h2 className="text-lg font-semibold mb-4">User Activity</h2>
            <div className="h-[300px] flex items-center justify-center border-2 border-dashed rounded-lg">
              <p className="text-muted-foreground">MetricUI chart placeholder</p>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
