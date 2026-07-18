import { TextInput, Textarea, Button, Stack, Select } from '@mantine/core';
import { useForm } from '@mantine/form';

const valoresPorDefecto = {
  schoolName: '',
  sector: '',
  priority: '',
  category: '',
  description: '',
};

export function SchoolClaimForm({
  initialValues = valoresPorDefecto,
  onSubmit,
  submitting = false,
  submitLabel = 'Enviar Reclamo',
}) {
  const form = useForm({
    initialValues,
    validate: {
      schoolName: (value) => (value.length < 3 ? 'Ingrese el nombre de la escuela' : null),
      sector: (value) => (value.length < 2 ? 'Ingrese el sector' : null),
      priority: (value) => (value === '' ? 'Seleccione una prioridad' : null),
      category: (value) => (value === '' ? 'Ingrese una categoría' : null),
      description: (value) => (value.length < 10 ? 'Describa el problema en detalle' : null),
    },
  });

  const handleSubmit = (values) => {
    onSubmit({
      nombre_escuela: values.schoolName,
      sector: values.sector,
      prioridad: values.priority,
      categoria: values.category,
      descripcion: values.description,
    });
  };

  return (
    <form onSubmit={form.onSubmit(handleSubmit)}>
      <Stack>
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

        <Button type="submit" mt="md" loading={submitting}>
          {submitLabel}
        </Button>
      </Stack>
    </form>
  );
}
