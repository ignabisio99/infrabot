import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Alert, Anchor, Container } from '@mantine/core';

import { SchoolClaimForm } from '../components/forms/SchoolClaimForm';
import { crearReclamo } from '../api/reclamos';

export function NewClaimPage() {
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState(null);
  const [enviadoOk, setEnviadoOk] = useState(false);
  const [formKey, setFormKey] = useState(0);

  const handleSubmit = async (payload) => {
    setError(null);
    setEnviadoOk(false);
    setEnviando(true);
    try {
      await crearReclamo(payload);
      setEnviadoOk(true);
      setFormKey((key) => key + 1);
    } catch (err) {
      setError(err.message);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <Container size="sm" py="xl">
      <Anchor component={Link} to="/reclamos" mb="md" display="inline-block">
        ← Volver a Reclamos
      </Anchor>

      {error && (
        <Alert color="red" title="No se pudo enviar el reclamo" mb="md">
          {error}
        </Alert>
      )}

      {enviadoOk && (
        <Alert color="green" title="Reclamo enviado" mb="md">
          Tu reclamo fue registrado correctamente.
        </Alert>
      )}

      <SchoolClaimForm key={formKey} onSubmit={handleSubmit} submitting={enviando} />
    </Container>
  );
}
