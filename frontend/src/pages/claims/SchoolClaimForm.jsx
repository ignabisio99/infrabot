import { useEffect, useState } from 'react';
import {
  Autocomplete,
  TextInput,
  Textarea,
  Button,
  Stack,
  Select,
  Group,
  Text,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { useDebouncedValue } from '@mantine/hooks';
import { IconMicrophone } from '@tabler/icons-react';

import { transcribirAudio } from '../../api/ai';
import { buscarInstituciones } from '../../api/instituciones';
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
      sector: (value) => (value.length < 2 ? 'Ingrese la dirección de la escuela' : null),
      priority: (value) => (value === '' ? 'Seleccione una prioridad' : null),
      category: (value) => (value === '' ? 'Ingrese una categoría' : null),
      description: (value) => (value.length < 10 ? 'Describa el problema en detalle' : null),
    },
  });

  const [escuelas, setEscuelas] = useState([]);
  const [consultaEscuela, setConsultaEscuela] = useState(initialValues.schoolName);
  const [consultaDebounced] = useDebouncedValue(consultaEscuela, 300);

  useEffect(() => {
    const consulta = consultaDebounced.trim();
    if (consulta.length < 2) return undefined;
    let vigente = true;
    // Si el padrón no responde se sigue pudiendo escribir la escuela a mano.
    buscarInstituciones(consulta)
      .then((resultado) => vigente && setEscuelas(resultado))
      .catch(() => vigente && setEscuelas([]));
    return () => {
      vigente = false;
    };
  }, [consultaDebounced]);

  const escuelaInputProps = form.getInputProps('schoolName');

  // Igual que en WhatsApp: la ubicación del reclamo es la dirección de la escuela en el
  // padrón; el aula o sector va en la descripción.
  const elegirEscuela = (nombre) => {
    const escuela = escuelas.find((e) => e.nombre === nombre);
    if (escuela?.domicilio) form.setFieldValue('sector', escuela.domicilio);
  };

  const aplicarTranscripcion = async (archivo) => {
    if (!archivo) return;
    setTranscribiendo(true);
    try {
      const resultado = await transcribirAudio(archivo);
      const actual = (form.values.description || '').trim();
      form.setFieldValue('description', actual ? `${actual}\n${resultado.texto}` : resultado.texto);
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
        <Autocomplete
          label="Escuela"
          placeholder="Buscá por número o nombre, ej: Primaria 10"
          data={
            consultaEscuela.trim().length < 2 ? [] : [...new Set(escuelas.map((e) => e.nombre))]
          }
          filter={({ options }) => options}
          key={form.key('schoolName')}
          {...escuelaInputProps}
          onChange={(valor) => {
            escuelaInputProps.onChange(valor);
            setConsultaEscuela(valor);
          }}
          onOptionSubmit={elegirEscuela}
        />

        <TextInput
          label="Ubicación"
          description="Dirección de la escuela. Se completa al elegirla del padrón; si no está, escribila."
          placeholder="Ejemplo: Mitre 5110"
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
            placeholder="Describa el problema y en qué parte de la escuela está (aula, piso, sector)..."
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
