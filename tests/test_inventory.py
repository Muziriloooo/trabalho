from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from conftest import TEST_HASH, token_from
from sentinela.extensions import db
from sentinela.models import AuditLog, Camera, CameraHealthEvent, ConnectionSecret, Organization, RoleAssignment, Site, User, utcnow
from sentinela.services import gateway, vault


@pytest.fixture
def inventory(app):
    with app.app_context():
        admin = db.session.scalar(select(User).where(User.email == "admin@example.test"))
        other = db.session.scalar(select(User).where(User.email == "other@example.test"))
        operator = db.session.scalar(select(User).where(User.email == "operator@example.test"))
        sites = [Site(name="Centro", identifier="centro", organization_id=admin.organization_id),
                 Site(name="Norte", identifier="norte", organization_id=admin.organization_id),
                 Site(name="Unidade de outro cliente", identifier="centro", organization_id=other.organization_id)]
        db.session.add_all(sites)
        db.session.flush()
        cameras = [Camera(name=f"Camera-{n}", identifier=f"cam-{n}", site_id=s.id, organization_id=s.organization_id,
                          protocol="demo", created_by=admin.id if n < 2 else other.id, location_description="Área autorizada") for n, s in enumerate(sites)]
        db.session.add_all(cameras)
        assignment = RoleAssignment(user_id=operator.id, organization_id=admin.organization_id, site_id=sites[0].id,
                                    role="operator", granted_by=admin.id)
        db.session.add(assignment)
        db.session.commit()
        return {"sites": [s.id for s in sites], "cameras": [c.id for c in cameras], "operator": operator.id,
                "admin": admin.id, "organization": admin.organization_id, "other_org": other.organization_id, "assignment": assignment.id}


def post(client, path, fields=None, token_path="/"):
    token = token_from(client.get(token_path))
    return client.post(path, data={"csrf_token": token, **(fields or {})})


def site_data(**overrides):
    return {"name": "Nova unidade", "identifier": "nova", "responsible": "Responsável local", "timezone": "America/Sao_Paulo",
            "address": "Endereço de teste", "location_description": "Local autorizado", "status": "active", **overrides}


def camera_data(site, **overrides):
    return {"name": "Nova câmera", "identifier": "nova", "site_id": site, "location_description": "Entrada",
            "protocol": "demo", "authorized": "y", **overrides}


def test_site_crud_filters_and_camera_counts(app, client, login, inventory):
    login()
    assert post(client, "/sites/new", site_data()).status_code == 302
    response = client.get("/sites?q=Nova")
    assert "Nova unidade" in response.text
    assert "Camera-2" not in response.text
    with app.app_context():
        site = db.session.scalar(select(Site).where(Site.identifier == "nova"))
        assert site.organization_id == inventory["organization"]
        site_id = site.id
    assert post(client, f"/sites/{site_id}/edit", site_data(name="Unidade alterada")).status_code == 302
    assert "Unidade alterada" in client.get("/sites").text
    assert post(client, "/sites/new", site_data()).status_code == 422
    assert post(client, "/sites/new", site_data(identifier="invalid-tz", timezone="Invalid/Zone")).status_code == 422
    assert post(client, f"/sites/{site_id}/edit", site_data(status="inactive")).status_code == 422
    assert post(client, f"/sites/{site_id}/edit", site_data(status="inactive", confirm="y")).status_code == 302
    assert "Nova unidade" in client.get("/sites?status=inactive").text


def test_untrusted_organization_ids_are_ignored(app, client, login, inventory):
    login()
    assert post(client, "/sites/new", site_data(organization_id=inventory["other_org"])).status_code == 302
    assert post(client, "/cameras/new", camera_data(inventory["sites"][0], organization_id=inventory["other_org"])).status_code == 302
    with app.app_context():
        assert db.session.scalar(select(Site).where(Site.identifier == "nova")).organization_id == inventory["organization"]
        assert db.session.scalar(select(Camera).where(Camera.identifier == "nova")).organization_id == inventory["organization"]


@pytest.mark.parametrize("resource", ["/sites/{site}/edit", "/cameras/{camera}", "/cameras/{camera}/edit", "/cameras/{camera}/status",
                                     "/cameras/{camera}/state", "/cameras/{camera}/delete", "/monitoring/{camera}/demo.mp4",
                                     "/monitoring/{camera}/media/index.m3u8", "/monitoring?camera={camera}"])
def test_cross_tenant_read_and_mutation_are_hidden(client, login, inventory, resource):
    login()
    path = resource.format(site=inventory["sites"][2], camera=inventory["cameras"][2])
    assert client.get(path).status_code == 404
    if path.endswith(("/edit", "/state", "/delete")):
        assert post(client, path, {"confirm": "y"}).status_code == 404


def test_camera_crud_and_explicit_delete(app, client, login, inventory):
    login()
    response = post(client, "/cameras/new", camera_data(inventory["sites"][0]))
    assert response.status_code == 302
    path = response.location
    assert post(client, "/cameras/new", camera_data(inventory["sites"][0])).status_code == 422
    assert post(client, path + "/edit", camera_data(inventory["sites"][1], name="Alterada")).status_code == 302
    assert "Alterada" in client.get(path).text
    assert post(client, path + "/state").status_code == 422
    assert post(client, path + "/state", {"confirm": "y"}).status_code == 302
    assert client.get(path + "/status").json["status"] == "disabled"
    assert post(client, path + "/delete", {"identifier": "errado"}).status_code == 422
    assert post(client, path + "/delete", {"identifier": "nova"}).status_code == 302
    assert client.get(path).status_code == 404
    with app.app_context():
        assert db.session.scalar(select(AuditLog.id).where(AuditLog.action == "camera.deleted"))


@pytest.mark.parametrize("overrides", [{"authorized": ""}, {"identifier": "bad/path"}, {"protocol": "ftp"}, {"protocol": "rtsp", "gateway_path": "http://evil"},
                                      {"protocol": "rtsp", "gateway_path": ""}, {"gateway_password": "without-user"}, {"gateway_username": "without-password"}])
def test_invalid_camera_configuration(client, login, inventory, overrides):
    login()
    assert post(client, "/cameras/new", camera_data(inventory["sites"][0], **overrides)).status_code == 422


def test_cross_site_camera_binding_blocked_in_form_and_database(app, client, login, inventory):
    login()
    assert post(client, "/cameras/new", camera_data(inventory["sites"][2])).status_code == 422
    with app.app_context():
        db.session.add(Camera(name="Invalid", identifier="bad", site_id=inventory["sites"][2], organization_id=inventory["organization"], created_by=inventory["admin"]))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()
        db.session.add(RoleAssignment(organization_id=inventory["organization"], user_id=inventory["operator"], site_id=inventory["sites"][2], role="operator"))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_operator_scope_applies_to_every_media_request(app, client, login, inventory):
    login("operator@example.test")
    first, second = inventory["cameras"][:2]
    assert "Camera-0" in client.get("/cameras").text
    assert "Camera-1" not in client.get("/cameras").text
    assert client.get(f"/cameras/{first}").status_code == 200
    assert client.get(f"/cameras/{second}").status_code == 404
    response = client.get(f"/monitoring/{first}/demo.mp4", headers={"Range": "bytes=0-63"})
    assert response.status_code == 206
    assert response.headers["Cache-Control"] == "no-store"
    assert len(response.data) == 64
    assert client.get(f"/monitoring/{second}/demo.mp4").status_code == 404
    assert client.get(f"/monitoring/{second}/media/index.m3u8").status_code == 404
    assert client.get("/cameras/new").status_code == 403
    assert post(client, f"/cameras/{first}/check").status_code == 403
    with app.app_context():
        db.session.delete(db.session.get(RoleAssignment, inventory["assignment"]))
        db.session.commit()
    assert client.get(f"/monitoring/{first}/demo.mp4", headers={"Range": "bytes=0-63"}).status_code == 404
    assert client.get(f"/cameras/{first}/status").status_code == 404


def test_inactive_site_and_disabled_camera_stop_media(app, client, login, inventory):
    login()
    camera_id = inventory["cameras"][0]
    with app.app_context():
        site = db.session.get(Site, inventory["sites"][0]); site.status = "inactive"; db.session.commit()
    assert client.get(f"/monitoring/{camera_id}/demo.mp4").status_code == 409
    assert post(client, f"/cameras/{camera_id}/check").status_code == 409
    assert client.get(f"/cameras/{camera_id}/status").json["status"] == "disabled"
    assert post(client, "/cameras/new", camera_data(inventory["sites"][0])).status_code == 422


def test_encrypted_credentials_never_return_to_frontend(app, client, login, inventory):
    login()
    response = post(client, "/cameras/new", camera_data(inventory["sites"][0], protocol="rtsp", gateway_path="authorized-source",
                                                       gateway_username="test-gateway-user", gateway_password="test-secret-for-vault-only"))
    assert response.status_code == 302
    path = response.location
    with app.app_context():
        camera = db.session.scalar(select(Camera).where(Camera.identifier == "nova"))
        secret = db.session.get(ConnectionSecret, camera.connection_secret_reference)
        assert b"test-secret-for-vault-only" not in secret.ciphertext
        assert vault.credentials(camera) == ("test-gateway-user", "test-secret-for-vault-only")
        reference = secret.id
    for page in [client.get(path), client.get(path + "/edit"), client.get("/cameras"), client.get("/monitoring")]:
        assert "test-secret-for-vault-only" not in page.text
        assert "test-gateway-user" not in page.text
        assert reference not in page.text
    # Campos vazios preservam; remoção exige opção explícita.
    assert post(client, path + "/edit", camera_data(inventory["sites"][0], protocol="rtsp", gateway_path="authorized-source")).status_code == 302
    with app.app_context():
        camera = db.session.scalar(select(Camera).where(Camera.identifier == "nova"))
        assert camera.connection_secret_reference == reference
    assert post(client, path + "/delete", {"identifier": "nova"}).status_code == 302
    with app.app_context():
        assert db.session.get(ConnectionSecret, reference) is None


def test_health_checks_history_limits_and_staleness(app, client, login, inventory, monkeypatch):
    login()
    camera_id = inventory["cameras"][0]
    path = f"/cameras/{camera_id}"
    assert post(client, path + "/check").status_code == 302
    assert client.get(path + "/status").json["status"] == "demo"
    with app.app_context():
        assert db.session.get(Camera, camera_id).last_seen_at is None
        assert db.session.scalar(select(CameraHealthEvent).where(CameraHealthEvent.camera_id == camera_id)).reason_code == "demo"
        camera = db.session.get(Camera, camera_id)
        camera.protocol = "rtsp"; camera.gateway_path = "test"; camera.last_checked_at = None; db.session.commit()
    monkeypatch.setattr(gateway, "probe", lambda camera: True)
    assert post(client, path + "/check").status_code == 302
    assert post(client, path + "/check").status_code == 429
    assert client.get(path + "/status").json["status"] == "online"
    with app.app_context():
        camera = db.session.get(Camera, camera_id)
        assert camera.last_seen_at is not None
        camera.last_checked_at = utcnow() - timedelta(seconds=100)
        db.session.commit()
    assert client.get(path + "/status").json["status"] == "unknown"
    monkeypatch.setattr(gateway, "probe", lambda camera: False)
    assert post(client, path + "/check").status_code == 302
    assert client.get(path + "/status").json["status"] == "offline"


def test_missing_gateway_is_inconclusive_not_fake_online(app, client, login, inventory):
    login()
    with app.app_context():
        camera = db.session.get(Camera, inventory["cameras"][0]); camera.protocol = "rtsp"; camera.gateway_path = "test"; db.session.commit()
    assert post(client, f"/cameras/{inventory['cameras'][0]}/check").status_code == 302
    with app.app_context():
        event = db.session.scalar(select(CameraHealthEvent))
        assert event.reason_code == "gateway_not_configured"
        assert event.event_type == "unknown"


def test_team_grant_revoke_and_inactive_account(app, client, login, inventory):
    login()
    assert post(client, "/team", {"user_id": inventory["operator"], "site_id": inventory["sites"][2], "role": "operator"}).status_code == 422
    assert post(client, "/team", {"user_id": inventory["operator"], "site_id": 0, "role": "supervisor"}).status_code == 302
    assert post(client, f"/team/scopes/{inventory['assignment']}/revoke", {"confirm": "y"}).status_code == 302
    assert post(client, "/team/new", {"email": "new@example.test", "password": "Testing-only-long-pass", "role": "operator"}).status_code == 302
    assert "new@example.test" in client.get("/team").text
    assert post(client, f"/team/{inventory['operator']}/state", {"confirm": "y"}).status_code == 302
    with app.app_context():
        assert not db.session.get(User, inventory["operator"]).active


def test_platform_manages_only_organization_metadata(client, login, inventory):
    login("platform@example.test")
    assert client.get("/organizations").status_code == 200
    assert post(client, "/organizations", {"name": "Nova empresa", "identifier": "new-org", "responsible": "Gestor", "status": "active"}, token_path="/organizations").status_code == 302
    assert client.get("/cameras").status_code == 403
    assert client.get(f"/monitoring/{inventory['cameras'][0]}/demo.mp4").status_code == 403


def test_org_admin_edits_only_own_organization(client, login, inventory):
    login()
    assert client.get("/organizations").status_code == 403
    assert client.get(f"/organizations/{inventory['other_org']}/edit").status_code == 403
    assert post(client, "/organization", {"name": "Atualizada", "identifier": "atualizada", "responsible": "Gestor", "status": "active"}).status_code == 302
    assert "Atualizada" in client.get("/organization").text


@pytest.mark.parametrize("path", ["/sites/new", "/cameras/new", "/organization", "/team", "/team/new"])
def test_management_requires_csrf(client, login, path):
    login()
    assert client.post(path, data={}).status_code == 400


def test_all_unit_scope_supervisor_and_revocation(app, client, login, inventory):
    with app.app_context():
        user = User(email="supervisor@example.test", organization_id=inventory["organization"], role="supervisor", password_hash=TEST_HASH)
        db.session.add(user); db.session.flush()
        grant = RoleAssignment(organization_id=inventory["organization"], user_id=user.id, role="supervisor", granted_by=inventory["admin"])
        db.session.add(grant); db.session.commit(); grant_id = grant.id
    login("supervisor@example.test")
    response = client.get("/cameras")
    assert "Camera-0" in response.text and "Camera-1" in response.text
    assert "Camera-2" not in response.text
    assert client.get("/team").status_code == 403
    assert post(client, "/sites/new", site_data()).status_code == 403
    with app.app_context():
        db.session.delete(db.session.get(RoleAssignment, grant_id)); db.session.commit()
    assert client.get(f"/cameras/{inventory['cameras'][0]}").status_code == 404


def test_revocation_blocks_hls_and_inactive_account(app, client, login, inventory):
    login("operator@example.test")
    camera_id = inventory["cameras"][0]
    with app.app_context():
        camera = db.session.get(Camera, camera_id); camera.protocol="rtsp"; camera.gateway_path="test"
        db.session.delete(db.session.get(RoleAssignment, inventory["assignment"])); db.session.commit()
    assert client.get(f"/monitoring/{camera_id}/media/index.m3u8").status_code == 404
    assert client.get(f"/monitoring/{camera_id}/media/segment0.mp4").status_code == 404
    with app.app_context():
        db.session.get(User, inventory["operator"]).active=False; db.session.commit()
    assert client.get(f"/cameras/{camera_id}/status").status_code == 302


def test_explicit_credential_removal_and_production_missing_key(app, client, login, inventory):
    login()
    response=post(client, "/cameras/new", camera_data(inventory["sites"][0],protocol="rtsp",gateway_path="test",gateway_username="test",gateway_password="test-password"))
    assert response.status_code == 302
    path=response.location
    assert post(client,path+"/edit",camera_data(inventory["sites"][0],protocol="rtsp",gateway_path="test",clear_credentials="y")).status_code == 302
    with app.app_context():
        camera=db.session.scalar(select(Camera).where(Camera.identifier=="nova"))
        assert camera.connection_secret_reference is None
        assert db.session.scalar(select(ConnectionSecret.id)) is None
    app.config.update(ENVIRONMENT="production", CAMERA_ENCRYPTION_KEY=None)
    response=post(client,path+"/edit",camera_data(inventory["sites"][0],protocol="rtsp",gateway_path="test",gateway_username="test",gateway_password="test-password"))
    assert response.status_code == 422
    assert "CAMERA_ENCRYPTION_KEY" in response.text


def test_secret_cannot_be_bound_to_camera_of_another_tenant(app, inventory):
    with app.app_context():
        secret=ConnectionSecret(organization_id=inventory["other_org"],ciphertext=b"not-a-valid-secret")
        db.session.add(secret); db.session.flush()
        camera=db.session.get(Camera,inventory["cameras"][0])
        camera.connection_secret_reference=secret.id
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_camera_delete_cascades_health_history(app, client, login, inventory):
    login()
    camera_id=inventory["cameras"][0]
    assert post(client,f"/cameras/{camera_id}/check").status_code == 302
    assert post(client,f"/cameras/{camera_id}/delete",{"identifier":"cam-0"}).status_code == 302
    with app.app_context():
        assert not db.session.scalars(select(CameraHealthEvent).where(CameraHealthEvent.camera_id==camera_id)).all()


def test_single_camera_and_site_filters_render(client, login, inventory):
    login()
    response=client.get(f"/monitoring?camera={inventory['cameras'][0]}")
    assert response.status_code == 200
    assert response.text.count('class="panel monitor-tile"') == 1
    assert "Camera-0" in response.text and "Camera-1" not in response.text
    response=client.get(f"/monitoring?site={inventory['sites'][1]}")
    assert response.status_code == 200
    assert "Camera-1" in response.text and "Camera-0" not in response.text
