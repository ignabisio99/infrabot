import { useState } from 'react';
import { TextInput, Textarea, Button, Stack, Select, Group, Text } from '@mantine/core';
import { useForm } from '@mantine/form';
import { IconMicrophone } from '@tabler/icons-react';

import { transcribirAudio } from '../../api/ai';
import { useGrabarAudio } from '../../hooks/useGrabarAudio';
import { notifyError, notifySuccess } from '../../utils/notifications';

const valoresPorDefecto = {
  schoolName: '',
  sector: '',
  priority: '',
  category: '',
  description: '',
  observations: '',
};

export function SchoolClaimForm({
  initialValues = valoresPorDefecto,
  onSubmit,
  submitting = false,
  submitLabel = 'Enviar Reclamo',
  children,
}) {
  const [transcribiendo, setTranscribiendo] = useState(false);
  const { grabando, empezar, detener } = useGrabarAudio();
  const form = useForm({
    initialValues,
    validate: {
      schoolName: (value) => (value.length < 3 ? 'Ingrese el nombre de la escuela' : null),
      sector: (value) => (value.length < 2 ? 'Ingrese la ubicación' : null),
      priority: (value) => (value === '' ? 'Seleccione una prioridad' : null),
      category: (value) => (value === '' ? 'Ingrese una categoría' : null),
      description: (value) => (value.length < 10 ? 'Describa el problema en detalle' : null),
    },
  });

  const aplicarTranscripcion = async (archivo) => {
    if (!archivo) return;
    setTranscribiendo(true);
    try {
      const resultado = await transcribirAudio(archivo);
      const actual = (form.values.description || '').trim();
      form.setFieldValue(
        'description',
        actual ? `${actual}\n${resultado.texto}` : resultado.texto,
      );
      notifySuccess('Audio transcrito. Revisá el texto antes de enviar.');
    } catch (error) {
      notifyError(error?.message || 'No se pudo transcribir el audio.');
    } finally {
      setTranscribiendo(false);
    }
  };

  const grabarYTranscribir = async () => {
    if (submitting || transcribiendo) return;
    try {
      if (!grabando) {
        await empezar();
        return;
      }
      const archivo = await detener();
      await aplicarTranscripcion(archivo);
    } catch (error) {
      notifyError(error?.message || 'No se pudo grabar el audio.');
    }
  };

  const handleSubmit = (values) => {
    onSubmit({
      nombre_escuela: values.schoolName,
      ubicacion: values.sector,
      prioridad: values.priority,
      categoria: values.category,
      descripcion: values.description,
      observaciones: values.observations.trim() === '' ? null : values.observations,
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
          label="Ubicación"
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

        <div>
          <Textarea
            label="Descripción"
            placeholder="Describa detalladamente la situación o problema detectado..."
            minRows={4}
            autosize
            key={form.key('description')}
            {...form.getInputProps('description')}
          />
          <Group mt={6} gap="xs">
            <Button
              type="button"
              size="xs"
              variant={grabando ? 'filled' : 'light'}
              color={grabando ? 'red' : 'teal'}
              leftSection={<IconMicrophone size={14} />}
              loading={transcribiendo}
              disabled={submitting}
              onClick={grabarYTranscribir}
            >
              {grabando ? 'Detener y transcribir' : 'Grabar audio'}
            </Button>
            <Text size="xs" c="dimmed">
              {grabando
                ? 'Grabando… hacé clic de nuevo para transcribir.'
                : 'Usa el micrófono. El audio no se guarda, solo el texto.'}
            </Text>
          </Group>
        </div>

        <Textarea
          label="Observaciones"
          placeholder="Notas adicionales (opcional)..."
          minRows={2}
          autosize
          key={form.key('observations')}
          {...form.getInputProps('observations')}
        />

        {children}

        <Button type="submit" mt="md" loading={submitting}>
          {submitLabel}
        </Button>
      </Stack>
    </form>
  );
}
