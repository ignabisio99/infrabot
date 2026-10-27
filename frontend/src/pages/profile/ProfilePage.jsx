import { useEffect, useState } from 'react';
import { Button, Container, Stack, Text, TextInput, Title } from '@mantine/core';
import { useForm } from '@mantine/form';

import { actualizarPerfil, getMe } from '../../api/auth';
import { CODIGOS_PAIS, componerTelefono, partirTelefono } from '../../components/PhoneInput';
import { notifyError, notifySuccess } from '../../utils/notifications';

export function ProfilePage() {
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [esContratista, setEsContratista] = useState(false);

  const form = useForm({
    initialValues: {
      nombre: '',
      telefono: '',
      direccion: '',
      nombre_empresa: '',
      especialidad: '',
    },
    validate: {
      nombre: (value) =>
        value.trim().length < 3 ? 'El nombre debe tener al menos 3 caracteres' : null,
      telefono: (value) =>
        (value || '').replace(/\D/g, '').length < 8 ? 'Ingresá un teléfono válido' : null,
      direccion: (value) => (value.trim().length < 5 ? 'Ingresá la dirección' : null),
      nombre_empresa: (value) =>
        esContratista && value.trim().length < 3
          ? 'El nombre de la empresa debe tener al menos 3 caracteres'
          : null,
      especialidad: (value) =>
        esContratista && value.trim().length < 2 ? 'Ingresá la especialidad' : null,
    },
  });

  useEffect(() => {
    getMe()
      .then((usuario) => {
        if (!usuario) return;
        setEsContratista(usuario.tipo === 'CONTRATISTA');
        form.setValues({
          nombre: usuario.nombre || '',
          telefono: usuario.telefono || '',
          direccion: usuario.direccion || '',
          nombre_empresa: usuario.nombre_empresa || '',
          especialidad: usuario.especialidad || '',
        });
      })
      .catch((err) => notifyError(err.message))
      .finally(() => setCargando(false));
  }, []);

  const handleSubmit = async (values) => {
    setGuardando(true);
    try {
      const actualizado = await actualizarPerfil({
        nombre: values.nombre.trim(),
        telefono: values.telefono.trim(),
        direccion: values.direccion.trim(),
        nombre_empresa: esContratista ? values.nombre_empresa.trim() : null,
        especialidad: esContratista ? values.especialidad.trim() : null,
      });
      localStorage.setItem('infrabot_user', JSON.stringify(actualizado));
      notifySuccess('Perfil actualizado.');
    } catch (err) {
      notifyError(err.message);
    } finally {
      setGuardando(false);
    }
  };

  return (
    <Container size="sm" px={0}>
      <Title order={2} mb="md">
        Mi perfil
      </Title>
      <Text size="sm" c="dimmed" mb="md">
        Estos datos se usan para contactarte. El email no se puede cambiar desde acá.
      </Text>

      <form onSubmit={form.onSubmit(handleSubmit)}>
        <Stack>
          <TextInput
            label="Nombre"
            disabled={cargando}
            key={form.key('nombre')}
            {...form.getInputProps('nombre')}
          />
          <div>
            <Text size="sm" fw={500} mb={4}>
              Teléfono{' '}
              <Text span c="red">
                *
              </Text>
            </Text>
            <Text size="xs" c="dimmed" mb={6}>
              Código de país: Argentina (+54) por defecto.
            </Text>
            <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start', width: '100%' }}>
              <select
                aria-label="Código de país"
                disabled={cargando}
                value={partirTelefono(form.values.telefono).codigo}
                onChange={(e) =>
                  form.setFieldValue(
                    'telefono',
                    componerTelefono(e.target.value, partirTelefono(form.values.telefono).nacional),
                  )
                }
                style={{
                  flex: '0 0 200px',
                  width: 200,
                  minWidth: 200,
                  height: 36,
                  padding: '0 8px',
                  borderRadius: 4,
                  border: '1px solid #ced4da',
                  background: '#fff',
                  fontSize: 14,
                }}
              >
                {CODIGOS_PAIS.map((pais) => (
                  <option key={pais.value} value={pais.value}>
                    {pais.label}
                  </option>
                ))}
              </select>
              <TextInput
                aria-label="Número de teléfono"
                placeholder="11 1234-5678"
                disabled={cargando}
                style={{ flex: '1 1 auto', minWidth: 140 }}
                value={partirTelefono(form.values.telefono).nacional}
                error={form.errors.telefono}
                onChange={(e) =>
                  form.setFieldValue(
                    'telefono',
                    componerTelefono(
                      partirTelefono(form.values.telefono).codigo,
                      e.currentTarget.value,
                    ),
                  )
                }
                onBlur={() => form.validateField('telefono')}
              />
            </div>
          </div>
          <TextInput
            label="Dirección"
            disabled={cargando}
            key={form.key('direccion')}
            {...form.getInputProps('direccion')}
          />
          {esContratista && (
            <>
              <TextInput
                label="Nombre de la empresa"
                disabled={cargando}
                key={form.key('nombre_empresa')}
                {...form.getInputProps('nombre_empresa')}
              />
              <TextInput
                label="Especialidad"
                disabled={cargando}
                key={form.key('especialidad')}
                {...form.getInputProps('especialidad')}
              />
            </>
          )}
          <Button type="submit" loading={guardando} disabled={cargando} w="fit-content">
            Guardar cambios
          </Button>
        </Stack>
      </form>
    </Container>
  );
}
