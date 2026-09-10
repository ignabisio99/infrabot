export const MATERIAL_VACIO = { description: '', quantity: '', unit: 'unidad', unitCost: '' };
export const LABOR_VACIA = { description: '', quantity: '', unitCost: '' };

function materialVacio(item) {
  return !item.description?.trim() && item.quantity === '' && item.unitCost === '';
}

function laborVacia(item) {
  return !item.description?.trim() && item.quantity === '' && item.unitCost === '';
}

export function partirItems(items) {
  const materials = [];
  const labor = [];
  for (const item of items ?? []) {
    if (item.tipo === 'MANO_OBRA') {
      labor.push({
        description: item.descripcion,
        quantity: item.cantidad,
        unitCost: item.costo_unitario,
      });
    } else {
      materials.push({
        description: item.descripcion,
        quantity: item.cantidad,
        unit: item.unidad ?? 'unidad',
        unitCost: item.costo_unitario,
      });
    }
  }
  return {
    materials: materials.length ? materials : [{ ...MATERIAL_VACIO }],
    labor: labor.length ? labor : [{ ...LABOR_VACIA }],
  };
}

export function serializarItems(materials, labor) {
  const items = [];
  for (const item of materials) {
    if (materialVacio(item)) continue;
    items.push({
      tipo: 'MATERIAL',
      descripcion: item.description,
      cantidad: item.quantity,
      unidad: item.unit || 'unidad',
      costo_unitario: item.unitCost,
    });
  }
  for (const item of labor) {
    if (laborVacia(item)) continue;
    items.push({
      tipo: 'MANO_OBRA',
      descripcion: item.description,
      cantidad: item.quantity,
      unidad: 'horas',
      costo_unitario: item.unitCost,
    });
  }
  return items;
}

export function totalLineas(materials, labor) {
  const sumar = (filas) =>
    filas.reduce(
      (acumulado, item) =>
        acumulado + (Number(item.quantity) || 0) * (Number(item.unitCost) || 0),
      0,
    );
  return sumar(materials) + sumar(labor);
}

export function validarLineasPresupuesto(materials, labor) {
  const errors = {};
  let hayCompleta = false;

  materials.forEach((item, index) => {
    if (materialVacio(item)) return;
    if (!item.description?.trim()) {
      errors[`materials.${index}.description`] = 'Ingrese el material';
    }
    if (item.quantity === '' || Number(item.quantity) <= 0) {
      errors[`materials.${index}.quantity`] = 'Debe ser mayor a 0';
    }
    if (!item.unit?.trim()) {
      errors[`materials.${index}.unit`] = 'Ingrese la unidad';
    }
    if (item.unitCost === '' || Number(item.unitCost) < 0) {
      errors[`materials.${index}.unitCost`] = 'No puede ser negativo';
    }
    if (
      item.description?.trim() &&
      Number(item.quantity) > 0 &&
      item.unit?.trim() &&
      item.unitCost !== '' &&
      Number(item.unitCost) >= 0
    ) {
      hayCompleta = true;
    }
  });

  labor.forEach((item, index) => {
    if (laborVacia(item)) return;
    if (!item.description?.trim()) {
      errors[`labor.${index}.description`] = 'Seleccione un rol';
    }
    if (item.quantity === '' || Number(item.quantity) <= 0) {
      errors[`labor.${index}.quantity`] = 'Debe ser mayor a 0';
    }
    if (item.unitCost === '' || Number(item.unitCost) < 0) {
      errors[`labor.${index}.unitCost`] = 'No puede ser negativo';
    }
    if (
      item.description?.trim() &&
      Number(item.quantity) > 0 &&
      item.unitCost !== '' &&
      Number(item.unitCost) >= 0
    ) {
      hayCompleta = true;
    }
  });

  if (!hayCompleta) {
    errors.lineas =
      'Agregá al menos un material o una línea de mano de obra.';
  }
  return errors;
}
