import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Alert, Anchor, Container } from '@mantine/core';

import { ContractorForm } from './ContractorForm';
import { crearContratista } from '../../api/contratistas';
import { notifyError } from '../../utils/notifications';

export function NewContractorPage() {
  const [enviando, setEnviando] = useState(false);
  const [enviadoOk, setEnviadoOk] = useState(false);
  const [formKey, setFormKey] = useState(0);

  const handleSubmit = async (payload) => {
    setEnviadoOk(false);
    setEnviando(true);
    try {
      await crearContratista(payload);
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
      <Anchor component={Link} to="/contratistas" mb="md" display="inline-block">
        ← Volver a Contratistas
      </Anchor>

      {enviadoOk && (
        <Alert color="green" title="Contratista guardado" mb="md">
          El contratista fue registrado correctamente.
        </Alert>
      )}

      <ContractorForm key={formKey} onSubmit={handleSubmit} submitting={enviando} />
    </Container>
  );
}
