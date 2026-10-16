import { Button, Checkbox, Input, Popover, Stack } from '@mantine/core';
import { useDisclosure, useId } from '@mantine/hooks';
import { IconChevronDown } from '@tabler/icons-react';

import { ESTADOS, etiquetaPorEstado as etiquetasReclamo } from './estados';

// Qué dice el botón según cuántos estados haya elegidos. Con uno solo se muestra su
// nombre; de dos en adelante no entran, así que va el conteo.
function resumen(estados, etiquetaPorEstado) {
  if (estados.length === 0) return 'Todos';
  if (estados.length === 1) return etiquetaPorEstado[estados[0]] ?? estados[0];
  return `${estados.length} estados`;
}

// Fijo y con lugar para la etiqueta más larga ("Pendiente de coordinación"): si el botón
// se adaptara al contenido, elegir un estado correría los filtros de al lado y la tabla.
const ANCHO = 260;

/**
 * Filtro de estado como botón que abre una lista de checkboxes.
 *
 * Es un botón y no un MultiSelect porque el campo crecía al apilar las etiquetas de cada
 * estado elegido y empujaba la tabla hacia abajo: acá el control mide siempre lo mismo,
 * haya cero u once estados marcados.
 *
 * Por defecto lista los estados de reclamo; Presupuestos le pasa los suyos.
 */
export function StatusFilterPopover({
  value,
  onChange,
  estados = ESTADOS,
  etiquetaPorEstado = etiquetasReclamo,
}) {
  const [abierto, { toggle, close }] = useDisclosure(false);
  // El id del wrapper se fija para poder referenciar el label desde el botón: Mantine lo
  // renderiza como `${id}-label`.
  const id = useId();

  return (
    <Input.Wrapper
      label="Estado"
      id={id}
      // Div y no <label>: Input.Wrapper le pone `htmlFor` apuntando al input que espera
      // como hijo, pero acá el hijo es un Button y encima Popover.Target le sobreescribe
      // el id con el suyo, así que el `for` quedaría colgado. El nombre accesible se lo
      // da el `aria-labelledby` del botón, y el onClick mantiene el click en el texto
      // "Estado" como en los filtros de al lado.
      labelElement="div"
      labelProps={{ onClick: toggle }}
      // El label de Input.Wrapper es inline-block, y el control acá es un Button
      // (inline-flex): sin esto quedan en la misma línea, mientras que el resto de los
      // filtros llevan el label arriba. La separación es la que Mantine le da al input
      // cuando hay label (--input-margin-top).
      styles={{
        label: {
          display: 'block',
          marginBottom: 'calc(var(--mantine-spacing-xs) / 2)',
          cursor: 'pointer',
        },
      }}
    >
      <Popover opened={abierto} onDismiss={close} position="bottom-start" shadow="md" withArrow>
        <Popover.Target>
          <Button
            aria-labelledby={`${id}-label`}
            variant="default"
            fw={400}
            justify="space-between"
            rightSection={<IconChevronDown size={16} stroke={1.5} />}
            onClick={toggle}
            w={ANCHO}
          >
            {resumen(value, etiquetaPorEstado)}
          </Button>
        </Popover.Target>

        <Popover.Dropdown>
          <Checkbox.Group value={value} onChange={onChange}>
            <Stack gap="xs">
              {estados.map((estado) => (
                <Checkbox key={estado} value={estado} label={etiquetaPorEstado[estado]} />
              ))}
            </Stack>
          </Checkbox.Group>

          {value.length > 0 && (
            <Button variant="subtle" size="xs" mt="sm" fullWidth onClick={() => onChange([])}>
              Limpiar estados
            </Button>
          )}
        </Popover.Dropdown>
      </Popover>
    </Input.Wrapper>
  );
}
