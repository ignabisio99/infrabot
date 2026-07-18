import { useState } from 'react';
import { TextInput, Textarea, Button, Stack, Select, Alert } from '@mantine/core';
import { useForm } from '@mantine/form';
import { crearReclamo } from '../../api/reclamos';

export function SchoolClaimForm() {
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState(null);
  const [enviadoOk, setEnviadoOk] = useState(false);

  const form = useForm({
    initialValues: {
      schoolName: '',
      sector: '',
      priority: '',
      category: '',
      description: '',
    },
    validate: {
      schoolName: (value) => (value.length < 3 ? 'Ingrese el nombre de la escuela' : null),
      sector: (value) => (value.length < 2 ? 'Ingrese el sector' : null),
      priority: (value) => (value === '' ? 'Seleccione una prioridad' : null),
      category: (value) => (value === '' ? 'Ingrese una categoría' : null),
      description: (value) => (value.length < 10 ? 'Describa el problema en detalle' : null),
    },
  });

  const handleSubmit = async (values) => {
    setError(null);
    setEnviadoOk(false);
    setEnviando(true);
    try {
      await crearReclamo({
        nombre_escuela: values.schoolName,
        sector: values.sector,
        prioridad: values.priority,
        categoria: values.category,
        descripcion: values.description,
      });
      form.reset();
      setEnviadoOk(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <form onSubmit={form.onSubmit(handleSubmit)}>
      <Stack>
        {error && (
          <Alert color="red" title="No se pudo enviar el reclamo">
            {error}
          </Alert>
        )}

        {enviadoOk && (
          <Alert color="green" title="Reclamo enviado">
            Tu reclamo fue registrado correctamente.
          </Alert>
        )}

        <TextInput
          label="Nombre de escuela"
          placeholder="Ejemplo: Escuela N° 123"
          key={form.key('schoolName')}
          {...form.getInputProps('schoolName')}
        />

        <TextInput
          label="Sector"
          placeholder="Ejemplo: Cocina, Baño, Aula 10"
          key={form.key('sector')}
          {...form.getInputProps('sector')}
        />

        <Select
          label="Prioridad"
          placeholder="Seleccione una opción"
          data={[
            { value: 'BAJA', label: 'Baja' },
            { value: 'MEDIA', label: 'Media' },
            { value: 'ALTA', label: 'Alta' },
          ]}
          key={form.key('priority')}
          {...form.getInputProps('priority')}
        />

        <TextInput
          label="Categoría"
          placeholder="Ejemplo: Gas, Electricidad..."
          key={form.key('category')}
          {...form.getInputProps('category')}
        />

        <Textarea
          label="Descripción"
          placeholder="Describa detalladamente la situación o problema detectado..."
          minRows={4}
          autosize
          key={form.key('description')}
          {...form.getInputProps('description')}
        />

        <Button type="submit" mt="md" loading={enviando}>
          Enviar Reclamo
        </Button>
      </Stack>
    </form>
  );
}
