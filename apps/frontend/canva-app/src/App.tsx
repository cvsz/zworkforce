import { useState, useEffect } from 'react'
import {
  AppUiProvider,
  Button,
  Rows,
  Text,
  Title,
  FormField,
  TextInput,
  Select,
  Option,
  Toggle,
  Badge,
  Divider,
} from '@canva/app-ui-kit'
import type { DesignEditorIntent } from '@canva/intents/design'
import { prepareDesignEditor } from '@canva/intents/design'

function DesignEditor() {
  const [title, setTitle] = useState('z-platform Dashboard')
  const [theme, setTheme] = useState('light')
  const [notifications, setNotifications] = useState(true)

  useEffect(() => {
    console.log('Canva App UI Kit mounted')
  }, [])

  return (
    <div style={{ padding: '16px', maxWidth: '400px' }}>
      <Rows spacing="2u">
        <Title>z-platform Dashboard</Title>
        <Text>
          Configure your dashboard settings. Changes sync with Canva design context.
        </Text>

        <Divider />

        <FormField
          label="Dashboard Title"
          value={title}
          control={(props) => (
            <TextInput
              {...props}
              onChange={(value) => setTitle(value)}
            />
          )}
        />

        <FormField
          label="Theme"
          control={(props) => (
            <Select
              {...props}
              value={theme}
              onValueChange={(value) => setTheme(value)}
            >
              <Option value="light">Light</Option>
              <Option value="dark">Dark</Option>
              <Option value="system">System</Option>
            </Select>
          )}
        />

        <FormField
          label="Notifications"
          control={(props) => (
            <Toggle
              {...props}
              checked={notifications}
              onChange={(checked) => setNotifications(checked)}
            />
          )}
        />

        <Rows spacing="1u">
          <Text variant="secondary">Status</Text>
          <Badge tone="success">Connected</Badge>
        </Rows>

        <Button
          variant="primary"
          stretch
          onClick={() => alert('Dashboard settings saved!')}
        >
          Save Settings
        </Button>
      </Rows>
    </div>
  )
}

const designEditor: DesignEditorIntent = {
  render: async () => {
    const rootElement = document.getElementById('root')
    if (!(rootElement instanceof Element)) {
      throw new Error('Unable to find element with id of root')
    }

    const root = ReactDOM.createRoot(rootElement)
    root.render(
      <AppUiProvider>
        <DesignEditor />
      </AppUiProvider>,
    )
  },
}

prepareDesignEditor(designEditor)
