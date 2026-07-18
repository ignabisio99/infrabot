import { Button, EmptyState } from '@mantine/core';

function App() {
  return (
    <EmptyState
      title="Infra Bot"
      description="Sistema de Gestión de Reclamos"
    >
      <EmptyState.Actions>
        <Button variant="default">Aceptar</Button>
      </EmptyState.Actions>
    </EmptyState>
  )
}

export default App
