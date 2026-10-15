import pytest

from models.usuario import TipoUsuario


@pytest.mark.parametrize("tipo", [TipoUsuario.ADMINISTRADOR, TipoUsuario.CONTRATISTA])
def test_admin_y_contratista_ven_la_agenda(client, loguear, tipo):
    loguear(tipo)

    assert client.get("/visitas").status_code == 200


def test_el_inspector_no_ve_la_agenda(client, loguear):
    loguear(TipoUsuario.INSPECTOR)

    assert client.get("/visitas").status_code == 403
