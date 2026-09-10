import { Input, NativeSelect, TextInput } from '@mantine/core';

export const CODIGOS_PAIS = [
  { value: '54', label: '+54 Argentina' },
  { value: '598', label: '+598 Uruguay' },
  { value: '55', label: '+55 Brasil' },
  { value: '56', label: '+56 Chile' },
  { value: '595', label: '+595 Paraguay' },
  { value: '591', label: '+591 Bolivia' },
  { value: '51', label: '+51 Perú' },
  { value: '593', label: '+593 Ecuador' },
  { value: '57', label: '+57 Colombia' },
  { value: '58', label: '+58 Venezuela' },
  { value: '52', label: '+52 México' },
  { value: '1', label: '+1 EE.UU. / Canadá' },
  { value: '34', label: '+34 España' },
  { value: '39', label: '+39 Italia' },
  { value: '351', label: '+351 Portugal' },
];

const CODIGOS_POR_LARGO = [...CODIGOS_PAIS].sort((a, b) => b.value.length - a.value.length);
const CODIGO_DEFAULT = '54';

function soloDigitos(valor) {
  return (valor || '').replace(/\D/g, '');
}

export function partirTelefono(valor) {
  const crudo = (valor || '').trim();
  const digitos = soloDigitos(crudo);
  if (!digitos) {
    return { codigo: CODIGO_DEFAULT, nacional: '' };
  }
  if (crudo.startsWith('+')) {
    const match = CODIGOS_POR_LARGO.find((item) => digitos.startsWith(item.value));
    if (match) {
      return { codigo: match.value, nacional: digitos.slice(match.value.length) };
    }
  }
  if (digitos.startsWith('54') && digitos.length > 10) {
    return { codigo: '54', nacional: digitos.slice(2) };
  }
  return { codigo: CODIGO_DEFAULT, nacional: digitos };
}

export function componerTelefono(codigo, nacional) {
  const numero = soloDigitos(nacional);
  if (!numero) return '';
  return `+${codigo || CODIGO_DEFAULT}${numero}`;
}

export function PhoneInput({
  label = 'Teléfono',
  description = 'El código de país por defecto es Argentina (+54).',
  placeholder = '11 1234-5678',
  required = false,
  disabled = false,
  error,
  value,
  onChange,
  onBlur,
}) {
  const { codigo, nacional } = partirTelefono(value);

  const emitir = (nuevoCodigo, nuevoNacional) => {
    onChange?.(componerTelefono(nuevoCodigo, nuevoNacional));
  };

  return (
    <Input.Wrapper label={label} description={description} required={required} error={error}>
      <div
        style={{
          display: 'flex',
          gap: 8,
          alignItems: 'flex-start',
          marginTop: 6,
          width: '100%',
        }}
      >
        <NativeSelect
          aria-label="Código de país"
          data={CODIGOS_PAIS}
          value={codigo}
          onChange={(e) => emitir(e.currentTarget.value, nacional)}
          disabled={disabled}
          style={{ flex: '0 0 200px', width: 200, minWidth: 200 }}
        />
        <TextInput
          aria-label="Número de teléfono"
          placeholder={placeholder}
          value={nacional}
          onChange={(e) => emitir(codigo, e.currentTarget.value)}
          onBlur={onBlur}
          disabled={disabled}
          error={Boolean(error)}
          style={{ flex: '1 1 auto', minWidth: 140 }}
        />
      </div>
    </Input.Wrapper>
  );
}
