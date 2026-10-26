import { useState } from 'react';
import {
  Alert,
  Anchor,
  Button,
  Container,
  Divider,
  Group,
  List,
  Paper,
  PasswordInput,
  Select,
  Stack,
  Tabs,
  Text,
  TextInput,
} from '@mantine/core';
import {
  IconAlertCircle,
  IconBuilding,
  IconCheck,
  IconLock,
  IconMail,
  IconMapPin,
  IconTool,
  IconUser,
} from '@tabler/icons-react';
import logo from '../../assets/logo-infrabot-front.png';
import { login, register, loginWithGoogle } from '../../api/auth';
import { PhoneInput } from '../../components/PhoneInput';
import { OlvidePasswordModal } from './OlvidePasswordModal';
import { GoogleLogin } from '@react-oauth/google';

export function LoginPage({ onLogin }) {
  const [activeTab, setActiveTab] = useState('login');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const [loginForm, setLoginForm] = useState({ email: '', password: '' });
  const [olvideAbierto, setOlvideAbierto] = useState(false);
  const [registerForm, setRegisterForm] = useState({
    nombre: '',
    email: '',
    password: '',
    confirmPassword: '',
    telefono: '',
    direccion: '',
    tipo: '',
    nombre_empresa: '',
    especialidad: '',
  });

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setLoading(true);
    try {
      const data = await login(loginForm.email, loginForm.password);
      localStorage.setItem('infrabot_user', JSON.stringify(data.usuario));
      onLogin();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    // Mismos mínimos que el backend, sin contar espacios.
    if (registerForm.nombre.trim().length < 3) {
      setError('El nombre debe tener al menos 3 caracteres');
      return;
    }
    if (registerForm.tipo === 'CONTRATISTA' && registerForm.nombre_empresa.trim().length < 3) {
      setError('El nombre de la empresa debe tener al menos 3 caracteres');
      return;
    }

    if (registerForm.password !== registerForm.confirmPassword) {
      setError('Las contraseñas no coinciden');
      return;
    }

    setLoading(true);
    try {
      const data = await register({
        nombre: registerForm.nombre,
        email: registerForm.email,
        password: registerForm.password,
        telefono: registerForm.telefono,
        direccion: registerForm.direccion,
        tipo: registerForm.tipo,
        nombre_empresa: registerForm.tipo === 'CONTRATISTA' ? registerForm.nombre_empresa : null,
        especialidad: registerForm.tipo === 'CONTRATISTA' ? registerForm.especialidad : null,
      });
      setSuccess(data.mensaje);
      setRegisterForm({
        nombre: '',
        email: '',
        password: '',
        confirmPassword: '',
        telefono: '',
        direccion: '',
        tipo: '',
        nombre_empresa: '',
        especialidad: '',
      });
      // Cambiar a la pestaña de login después de registrarse
      setTimeout(() => setActiveTab('login'), 3000);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSuccess = async (credentialResponse) => {
    setError('');
    setSuccess('');
    setLoading(true);
    try {
      const data = await loginWithGoogle(credentialResponse.credential);
      localStorage.setItem('infrabot_user', JSON.stringify(data.usuario));
      onLogin();
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
      <Container size={440}>
        <Stack align="center" mb="lg">
          <img
            src={logo}
            alt="InfraBot"
            height={72}
            style={{ borderRadius: 12, boxShadow: '0 4px 12px rgba(0,0,0,0.3)' }}
          />
          <Text c="rgba(255,255,255,0.7)" ta="center" size="sm">
            Sistema de gestión de reclamos de infraestructura escolar
          </Text>
        </Stack>

        <Paper radius="md" p="xl" shadow="xl" withBorder>
          {import.meta.env.VITE_GOOGLE_CLIENT_ID ? (
            <>
              <Stack align="center" mb="md">
                <GoogleLogin
                  onSuccess={handleGoogleSuccess}
                  onError={() => setError('Error al iniciar sesión con Google')}
                  text="continue_with"
                  shape="pill"
                  width="100%"
                />
              </Stack>
              <Divider label="o con email" labelPosition="center" mb="md" />
            </>
          ) : null}

          <Tabs
            value={activeTab}
            onChange={(v) => {
              setActiveTab(v);
              setError('');
              setSuccess('');
            }}
          >
            <Tabs.List grow mb="md">
              <Tabs.Tab value="login">Iniciar sesión</Tabs.Tab>
              <Tabs.Tab value="register">Registrarse</Tabs.Tab>
            </Tabs.List>

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

            <Tabs.Panel value="login">
              <form onSubmit={handleLogin}>
                <Stack>
                  <TextInput
                    label="Email"
                    placeholder="tu@email.com"
                    leftSection={<IconMail size={16} />}
                    required
                    value={loginForm.email}
                    onChange={(e) => setLoginForm({ ...loginForm, email: e.target.value })}
                  />
                  <PasswordInput
                    label="Contraseña"
                    placeholder="Tu contraseña"
                    leftSection={<IconLock size={16} />}
                    required
                    value={loginForm.password}
                    onChange={(e) => setLoginForm({ ...loginForm, password: e.target.value })}
                  />
                  <Group justify="flex-end">
                    <Anchor
                      component="button"
                      type="button"
                      size="xs"
                      c="#1fa7b3"
                      onClick={() => setOlvideAbierto(true)}
                    >
                      ¿Olvidaste tu contraseña?
                    </Anchor>
                  </Group>
                  <Button type="submit" fullWidth color="#1fa7b3" loading={loading}>
                    Iniciar sesión
                  </Button>
                </Stack>
              </form>
            </Tabs.Panel>

            <Tabs.Panel value="register">
              <form onSubmit={handleRegister}>
                <Stack>
                  <TextInput
                    label="Nombre completo"
                    placeholder="Tu nombre"
                    leftSection={<IconUser size={16} />}
                    required
                    value={registerForm.nombre}
                    onChange={(e) => setRegisterForm({ ...registerForm, nombre: e.target.value })}
                  />
                  <TextInput
                    label="Email"
                    placeholder="tu@email.com"
                    leftSection={<IconMail size={16} />}
                    required
                    value={registerForm.email}
                    onChange={(e) => setRegisterForm({ ...registerForm, email: e.target.value })}
                  />
                  <PasswordInput
                    label="Contraseña"
                    placeholder="Mínimo 8 caracteres"
                    leftSection={<IconLock size={16} />}
                    required
                    value={registerForm.password}
                    onChange={(e) => setRegisterForm({ ...registerForm, password: e.target.value })}
                  />
                  <List size="xs" c="dimmed" spacing={4}>
                    <List.Item>Mínimo 8 caracteres</List.Item>
                    <List.Item>Al menos una mayúscula</List.Item>
                    <List.Item>Al menos un símbolo especial (!@#$%...)</List.Item>
                  </List>
                  <PasswordInput
                    label="Confirmar contraseña"
                    placeholder="Repetí tu contraseña"
                    leftSection={<IconLock size={16} />}
                    required
                    value={registerForm.confirmPassword}
                    onChange={(e) =>
                      setRegisterForm({ ...registerForm, confirmPassword: e.target.value })
                    }
                  />

                  <Divider label="Datos de perfil" labelPosition="center" />

                  <PhoneInput
                    label="Teléfono de contacto"
                    required
                    value={registerForm.telefono}
                    onChange={(telefono) => setRegisterForm({ ...registerForm, telefono })}
                  />
                  <TextInput
                    label="Dirección"
                    placeholder="Av. Medrano 951, CABA"
                    leftSection={<IconMapPin size={16} />}
                    required
                    value={registerForm.direccion}
                    onChange={(e) =>
                      setRegisterForm({ ...registerForm, direccion: e.target.value })
                    }
                  />
                  <Select
                    label="Tipo de usuario"
                    placeholder="Seleccioná tu rol"
                    required
                    data={[
                      { value: 'ADMINISTRADOR', label: 'Administrador' },
                      { value: 'CONTRATISTA', label: 'Contratista' },
                      { value: 'INSPECTOR', label: 'Inspector' },
                    ]}
                    value={registerForm.tipo}
                    onChange={(value) => setRegisterForm({ ...registerForm, tipo: value })}
                  />
                  {registerForm.tipo === 'CONTRATISTA' && (
                    <>
                      <TextInput
                        label="Nombre de la empresa"
                        placeholder="Mi Empresa S.A."
                        leftSection={<IconBuilding size={16} />}
                        required
                        value={registerForm.nombre_empresa}
                        onChange={(e) =>
                          setRegisterForm({ ...registerForm, nombre_empresa: e.target.value })
                        }
                      />
                      <TextInput
                        label="Especialidad"
                        placeholder="Electricidad, Plomería, etc."
                        leftSection={<IconTool size={16} />}
                        required
                        value={registerForm.especialidad}
                        onChange={(e) =>
                          setRegisterForm({ ...registerForm, especialidad: e.target.value })
                        }
                      />
                    </>
                  )}

                  <Button type="submit" fullWidth color="#1fa7b3" loading={loading}>
                    Registrarse
                  </Button>
                </Stack>
              </form>
            </Tabs.Panel>
          </Tabs>

          <Divider my="md" />
          <Text ta="center" size="xs" c="dimmed">
            © {new Date().getFullYear()} InfraBot UTN
          </Text>
        </Paper>
      </Container>

      {/* Se monta al abrir: así arranca con el email que ya estaba escrito en el login. */}
      {olvideAbierto && (
        <OlvidePasswordModal
          opened
          onClose={() => setOlvideAbierto(false)}
          emailInicial={loginForm.email}
        />
      )}
    </div>
  );
}
