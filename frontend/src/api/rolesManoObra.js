import { crearRecursoApi } from './apiClient';

export const {
  listar: listarRolesManoObra,
  crear: crearRolManoObra,
  actualizar: actualizarRolManoObra,
  eliminar: eliminarRolManoObra,
} = crearRecursoApi({
  recursoPlural: 'roles-mano-obra',
  recursoSingular: 'rol de mano de obra',
});
