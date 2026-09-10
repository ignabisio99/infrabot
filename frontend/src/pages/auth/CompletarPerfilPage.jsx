import { useState } from 'react';
import {
  Alert,
  Button,
  Container,
  Paper,
  Select,
  Stack,
  Text,
  TextInput,
} from '@mantine/core';
import {
  IconAlertCircle,
  IconBuilding,
  IconCheck,
  IconMapPin,
  IconTool,
} from '@tabler/icons-react';
import logo from '../../assets/logo-infrabot-front.png';
import { API_URL, extraerMensajeError } from '../../api/apiClient';
import { PhoneInput } from '../../components/PhoneInput';

export function CompletarPerfilPage({ usuario, onComplete }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const [form, setForm] = useState({
    telefono: '',
    direccion: '',
    tipo: '',
    nombre_empresa: '',
    especialidad: '',
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const body = {
        telefono: form.telefono,
        direccion: form.direccion,
        tipo: form.tipo,
      };

      if (form.tipo === 'CONTRATISTA') {
        body.nombre_empresa = form.nombre_empresa;
        body.especialidad = form.especialidad;
      }

      const response = await fetch(`${API_URL}/auth/completar-perfil/${usuario.id}`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error(extraerMensajeError(data?.detail, 'Error al completar el perfil'));
      }

      const data = await response.json();
      setSuccess(data.mensaje);

      const updatedUser = {
        ...usuario,
        estado: 'PENDIENTE_APROBACION',
        tipo: form.tipo,
      };
      localStorage.setItem('infrabot_user', JSON.stringify(updatedUser));

      setTimeout(() => onComplete(), 2000);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        background: 'linear-gradient(135deg, #132a4d 0%, #1a3a5c 50%, #1fa7b3 100%)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <Container size={480}>
        <Stack align="center" mb="lg">
          <img
            src={logo}
            alt="InfraBot"
            height={72}
            style={{ borderRadius: 12, boxShadow: '0 4px 12px rgba(0,0,0,0.3)' }}
          />
          <Text c="rgba(255,255,255,0.7)" ta="center" size="sm">
            Completá tu perfil para continuar
          </Text>
        </Stack>

        <Paper radius="md" p="xl" shadow="xl" withBorder>
          {error && (
            <Alert icon={<IconAlertCircle size={16} />} color="red" mb="md" variant="light">
              {error}
            </Alert>
          )}

          {success && (
            <Alert icon={<IconCheck size={16} />} color="green" mb="md" variant="light">
              {success}
            </Alert>
          )}

          {!success && (
            <form onSubmit={handleSubmit}>
              <Stack>
                <PhoneInput
                  label="Teléfono de contacto"
                  required
                  value={form.telefono}
                  onChange={(telefono) => setForm({ ...form, telefono })}
                />

                <TextInput
                  label="Dirección"
                  placeholder="Av. Medrano 951, CABA"
                  leftSection={<IconMapPin size={16} />}
                  required
                  value={form.direccion}
                  onChange={(e) => setForm({ ...form, direccion: e.target.value })}
                />

                <Select
                  label="Tipo de usuario"
                  placeholder="Seleccioná tu rol"
                  required
                  data={[
                    { value: 'ADMINISTRADOR', label: 'Administrador' },
                    { value: 'CONTRATISTA', label: 'Contratista' },
                  ]}
                  value={form.tipo}
                  onChange={(value) => setForm({ ...form, tipo: value })}
                />

                {form.tipo === 'CONTRATISTA' && (
                  <>
                    <TextInput
                      label="Nombre de la empresa"
                      placeholder="Mi Empresa S.A."
                      leftSection={<IconBuilding size={16} />}
                      required
                      value={form.nombre_empresa}
                      onChange={(e) => setForm({ ...form, nombre_empresa: e.target.value })}
                    />
                    <TextInput
                      label="Especialidad"
                      placeholder="Electricidad, Plomería, etc."
                      leftSection={<IconTool size={16} />}
                      required
                      value={form.especialidad}
                      onChange={(e) => setForm({ ...form, especialidad: e.target.value })}
                    />
                  </>
                )}

                <Button type="submit" fullWidth color="#1fa7b3" loading={loading}>
                  Completar perfil
                </Button>
              </Stack>
            </form>
          )}
        </Paper>
      </Container>
    </div>
  );
}
