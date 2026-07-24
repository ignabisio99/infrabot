import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Alert, Anchor, Container } from '@mantine/core';

import { SchoolClaimForm } from '../components/forms/SchoolClaimForm';
import { crearReclamo } from '../api/reclamos';
import { notifyError } from '../utils/notifications';

export function NewClaimPage() {
  const [enviando, setEnviando] = useState(false);
  const [enviadoOk, setEnviadoOk] = useState(false);
  const [formKey, setFormKey] = useState(0);

  const handleSubmit = async (payload) => {
    setEnviadoOk(false);
    setEnviando(true);
    try {
      await crearReclamo(payload);
      setEnviadoOk(true);
      setFormKey((key) => key + 1);
    } catch (error) {
      notifyError(error?.message);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <Container size="sm" py="xl">
      <Anchor component={Link} to="/reclamos" mb="md" display="inline-block">
        ← Volver a Reclamos
      </Anchor>

      {enviadoOk && (
        <Alert color="green" title="Reclamo enviado" mb="md">
          Tu reclamo fue registrado correctamente.
        </Alert>
      )}

      <SchoolClaimForm key={formKey} onSubmit={handleSubmit} submitting={enviando} />
    </Container>
  );
}
