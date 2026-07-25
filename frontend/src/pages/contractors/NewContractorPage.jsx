import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Anchor, Container } from '@mantine/core';

import { ContractorForm } from './ContractorForm';
import { crearContratista } from '../../api/contratistas';
import { notifyError, notifySuccess } from '../../utils/notifications';

export function NewContractorPage() {
  const [enviando, setEnviando] = useState(false);
  const [formKey, setFormKey] = useState(0);

  const handleSubmit = async (payload) => {
    setEnviando(true);
    try {
      await crearContratista(payload);
      notifySuccess('El contratista fue registrado correctamente.');
      setFormKey((key) => key + 1);
    } catch (error) {
      notifyError(error?.message);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <Container size="sm" py="xl">
      <Anchor component={Link} to="/contratistas" mb="md" display="inline-block">
        ← Volver a Contratistas
      </Anchor>

      <ContractorForm key={formKey} onSubmit={handleSubmit} submitting={enviando} />
    </Container>
  );
}
