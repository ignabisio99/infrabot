import { TextInput, Textarea, Button, Stack, Container } from '@mantine/core';
import { useForm } from '@mantine/form';

export function SchoolClaimForm() {
  const form = useForm({
    initialValues: {
      schoolName: '',
      sector: '',
      description: '',
    },
    validate: {
      schoolName: (value) => (value.length < 3 ? 'Ingrese el nombre de la escuela' : null),
      sector: (value) => (value.length < 2 ? 'Ingrese el sector' : null),
      description: (value) => (value.length < 10 ? 'Describa el problema en detalle' : null),
    },
  });

  const handleSubmit = (values) => {
    console.log('Form submitted:', values);
    // Logic to handle submission will go here
  };

  return (
    <Container size="sm" py="xl">
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

        <Textarea
          label="Descripción"
          placeholder="Describa detalladamente la situación o problema detectado..."
          minRows={4}
          autosize
          key={form.key('description')}
          {...form.getInputProps('description')}
        />

        <Button type="submit" mt="md">
          Enviar Reclamo
        </Button>
      </Stack>
    </form>
  </Container>
  );
}
