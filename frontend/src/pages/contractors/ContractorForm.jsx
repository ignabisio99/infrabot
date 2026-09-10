import { TextInput, Select, Textarea, Button, Stack } from '@mantine/core';
import { useForm } from '@mantine/form';

import { PhoneInput } from '../../components/PhoneInput';

const valoresPorDefecto = {
  companyName: '',
  phone: '',
  address: '',
  specialty: '',
  rating: '',
  ratingNotes: '',
};

const OPCIONES_CALIFICACION = [
  { value: '1', label: '1' },
  { value: '2', label: '2' },
  { value: '3', label: '3' },
  { value: '4', label: '4' },
  { value: '5', label: '5' },
];

export function ContractorForm({
  initialValues = valoresPorDefecto,
  onSubmit,
  submitting = false,
  submitLabel = 'Guardar Contratista',
}) {
  const form = useForm({
    initialValues,
    validate: {
      companyName: (value) => (value.length < 3 ? 'Ingrese el nombre de la empresa' : null),
      phone: (value) =>
        (value || '').replace(/\D/g, '').length < 8 ? 'Ingrese un teléfono válido' : null,
      address: (value) => (value.length < 3 ? 'Ingrese la dirección' : null),
      specialty: (value) => (value.length < 2 ? 'Ingrese la especialidad' : null),
    },
  });

  const handleSubmit = (values) => {
    onSubmit({
      nombre_empresa: values.companyName,
      telefono: values.phone,
      direccion: values.address,
      especialidad: values.specialty,
      // Vacío = N/A (null); el backend lo acepta como opcional.
      calificacion: values.rating === '' || values.rating == null ? null : Number(values.rating),
      observaciones_calificacion:
        values.ratingNotes && values.ratingNotes.trim() !== '' ? values.ratingNotes : null,
    });
  };

  return (
    <form onSubmit={form.onSubmit(handleSubmit)}>
      <Stack>
        <TextInput
          label="Nombre de la empresa"
          placeholder="Ejemplo: Gas Sur SRL"
          key={form.key('companyName')}
          {...form.getInputProps('companyName')}
        />

        <PhoneInput
          value={form.values.phone}
          error={form.errors.phone}
          onChange={(telefono) => form.setFieldValue('phone', telefono)}
          onBlur={() => form.validateField('phone')}
        />

        <TextInput
          label="Dirección"
          placeholder="Ejemplo: Av. Rivadavia 1234"
          key={form.key('address')}
          {...form.getInputProps('address')}
        />

        <TextInput
          label="Especialidad"
          placeholder="Ejemplo: Gas, Electricidad, Plomería..."
          key={form.key('specialty')}
          {...form.getInputProps('specialty')}
        />

        <Select
          label="Calificación"
          description="Opcional. Dejala vacía si todavía no fue asignada (N/A)."
          placeholder="Seleccioná del 1 al 5"
          data={OPCIONES_CALIFICACION}
          clearable
          key={form.key('rating')}
          {...form.getInputProps('rating')}
        />

        <Textarea
          label="Observaciones de la calificación"
          description="Opcional. Anotá algo específico sobre este contratista."
          placeholder="Ej: cumplió en tiempo y forma en trabajos anteriores"
          minRows={2}
          autosize
          key={form.key('ratingNotes')}
          {...form.getInputProps('ratingNotes')}
        />

        <Button type="submit" mt="md" loading={submitting}>
          {submitLabel}
        </Button>
      </Stack>
    </form>
  );
}
