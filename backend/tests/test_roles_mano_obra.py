from datetime import datetime, timezone

from core.dependencies import get_current_user
from models.presupuesto import ItemPresupuesto, TipoItemPresupuesto
from models.rol_mano_obra import RolManoObra
from models.usuario import TipoUsuario, Usuario
from main import app


def test_crud_rol_y_no_borra_si_esta_en_uso(client, db, crear_reclamo, crear_presupuesto_aprobado):
    admin = Usuario(
        nombre="Admin roles",
        email="admin-roles@test.local",
        password_hash="x",
        tipo=TipoUsuario.ADMINISTRADOR,
    )
    db.add(admin)
    db.flush()
    app.dependency_overrides[get_current_user] = lambda: admin

    creado = client.post("/roles-mano-obra", json={"nombre": "Yesero"}).json()
    assert creado["nombre"] == "Yesero"

    listado = client.get("/roles-mano-obra").json()
    assert any(rol["nombre"] == "Yesero" for rol in listado)

    reclamo = crear_reclamo()
    presupuesto = crear_presupuesto_aprobado(
        reclamo, items=[(2, 1000)], fecha_aprobacion=datetime.now(timezone.utc)
    )
    db.add(
        ItemPresupuesto(
            presupuesto_id=presupuesto.id,
            tipo=TipoItemPresupuesto.MANO_OBRA,
            descripcion="Yesero",
            cantidad=1,
            unidad="horas",
            costo_unitario=1000,
        )
    )
    db.flush()

    respuesta = client.delete(f"/roles-mano-obra/{creado['id']}")
    assert respuesta.status_code == 409

    client.put(f"/roles-mano-obra/{creado['id']}", json={"nombre": "Yesero senior"})
    assert db.get(RolManoObra, creado["id"]).nombre == "Yesero senior"
