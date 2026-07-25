import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Anchor, Container } from '@mantine/core';

import { SchoolClaimForm } from './SchoolClaimForm';
import { crearReclamo } from '../../api/reclamos';
import { notifyError, notifySuccess } from '../../utils/notifications';

export function NewClaimPage() {
  const [enviando, setEnviando] = useState(false);
  const [formKey, setFormKey] = useState(0);

  const handleSubmit = async (payload) => {
    setEnviando(true);
    try {
      await crearReclamo(payload);
      notifySuccess('Tu reclamo fue registrado correctamente.');
      setFormKey((key) => key + 1);
    } catch (error) {
      notifyError(error?.message);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <Container size="sm" px={0}>
      <Anchor component={Link} to="/reclamos" mb="md" display="inline-block">
        ← Volver a Reclamos
      </Anchor>

      <SchoolClaimForm key={formKey} onSubmit={handleSubmit} submitting={enviando} />
    </Container>
  );
}
