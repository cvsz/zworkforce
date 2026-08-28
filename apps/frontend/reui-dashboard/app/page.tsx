import { Metadata } from 'next'
import { Button, Card, Text, Heading, Stack } from '@nuka-ui/core'
import '@nuka-ui/core/styles'

export const metadata: Metadata = {
  title: 'Dashboard',
  description: 'z-platform ReUI Dashboard',
}

export default function DashboardPage() {
  return (
    <div className="min-h-screen bg-canvas">
      <header className="border-b">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <h1 className="text-2xl font-bold">z-platform Dashboard</h1>
          <nav className="flex items-center gap-4">
            <Button variant="ghost">Overview</Button>
            <Button variant="ghost">Analytics</Button>
            <Button variant="ghost">Settings</Button>
          </nav>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <Card>
            <Stack gap="sm">
              <Text className="text-sm font-medium text-muted">Total Users</Text>
              <div className="text-3xl font-bold">12,345</div>
              <Text className="text-xs text-muted">+20.1% from last month</Text>
            </Stack>
          </Card>

          <Card>
            <Stack gap="sm">
              <Text className="text-sm font-medium text-muted">Revenue</Text>
              <div className="text-3xl font-bold">$45,231</div>
              <Text className="text-xs text-muted">+15.3% from last month</Text>
            </Stack>
          </Card>

          <Card>
            <Stack gap="sm">
              <Text className="text-sm font-medium text-muted">Active Sessions</Text>
              <div className="text-3xl font-bold">1,234</div>
              <Text className="text-xs text-muted">+5.2% from last hour</Text>
            </Stack>
          </Card>

          <Card>
            <Stack gap="sm">
              <Text className="text-sm font-medium text-muted">API Calls</Text>
              <div className="text-3xl font-bold">892K</div>
              <Text className="text-xs text-muted">+12.5% from yesterday</Text>
            </Stack>
          </Card>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card>
            <Stack gap="sm">
              <Heading as="h2">Analytics Overview</Heading>
              <Text className="text-muted">Platform performance metrics for the last 7 days</Text>
              <div className="h-[300px] flex items-center justify-center border-2 border-dashed rounded-lg">
                <Text className="text-muted">Chart placeholder — integrate nuka-ui charts</Text>
              </div>
            </Stack>
          </Card>

          <Card>
            <Stack gap="sm">
              <Heading as="h2">Recent Activity</Heading>
              <Text className="text-muted">Latest platform events</Text>
              <div className="h-[300px] flex items-center justify-center border-2 border-dashed rounded-lg">
                <Text className="text-muted">Activity feed placeholder — integrate nuka-ui timeline</Text>
              </div>
            </Stack>
          </Card>
        </div>
      </main>
    </div>
  )
}
