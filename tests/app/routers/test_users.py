from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.roles import RoleName
from app.core.security import _auth_user_cache_key, get_current_user, require_admin
from app.main import app
from app.models.auth.role import Role
from app.models.auth.user import User
from app.models.auth.user_session import UserSession
from app.models.career import Career
from app.models.club.club import Club
from app.models.club.club_join_request import ClubJoinRequest
from app.models.club.club_member import ClubMember
from app.models.club.event import ClubEvent
from app.models.club.message import ClubMessage
from app.models.club.post import ClubPost
from app.models.club.post_comment import ClubPostComment
from app.models.club.post_image import ClubPostImage
from app.models.club.post_like import ClubPostLike
from app.models.complaint.complaint import (
    Complaint,
    ComplaintCategory,
    ComplaintStatus,
    ComplaintType,
)
from app.models.complaint.complaint_image import ComplaintImage
from app.models.moderation.content_report import (
    ContentReport,
    ContentReportReason,
    ContentTargetType,
)
from app.models.moderation.user_block import UserBlock
from app.models.notification.notification import (
    Notification,
    NotificationCategory,
    NotificationEventType,
)
from app.schemas.auth.auth import CurrentUser


def test_me_returns_current_user(db, clear_dependency_overrides, monkeypatch):
    role = db.query(Role).filter(Role.name == RoleName.USER).one_or_none()
    if not role:
        role = Role(name=RoleName.USER)
        db.add(role)
        db.commit()

    user = User(
        email="test@itmexicali.edu.mx",
        name="Test User",
        oauth_provider="google",
        oauth_sub="1",
        id_role=role.id,
    )
    db.add(user)
    db.commit()

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=user.id,
        role=RoleName.USER,
    )

    monkeypatch.setattr(
        "app.routers.auth.users.cache_service.get_json_with_status",
        lambda _key: (None, "bypass"),
    )
    monkeypatch.setattr(
        "app.routers.auth.users.cache_service.set_json",
        lambda _key, _value, _ttl: None,
    )

    client = TestClient(app)

    response = client.get("/users/me")

    # Keep this test deterministic and independent from external Redis state.
    assert response.status_code == 200
    assert response.headers["x-cache"] == "BYPASS"
    assert response.json() == {
        "id": user.id,
        "email": "test@itmexicali.edu.mx",
        "role": RoleName.USER,
        "name": "Test User",
        "clubs_count": 0,
        "complaints_count": 0,
        "likes_count": 0,
        "career": None,
        "photo": None,
    }


def test_me_returns_404_when_user_does_not_exist(clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=9999,
        role=RoleName.USER,
    )
    client = TestClient(app)

    response = client.get("/users/me")

    assert response.status_code == 404
    assert response.json()["detail"] == "Usuario no encontrado"


def test_me_returns_cached_payload(clear_dependency_overrides, monkeypatch):
    cached_payload = {
        "id": 42,
        "email": "cached@itmexicali.edu.mx",
        "role": RoleName.USER,
        "name": "Cached User",
        "clubs_count": 3,
        "complaints_count": 1,
        "likes_count": 0,
        "career": "Ingeniería en Sistemas",
        "photo": "https://cdn.example/users/42/photo.png",
    }

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=42,
        role=RoleName.USER,
    )
    monkeypatch.setattr(
        "app.routers.auth.users.cache_service.get_json_with_status",
        lambda _key: (cached_payload, "hit"),
    )

    client = TestClient(app)
    response = client.get("/users/me")

    assert response.status_code == 200
    assert response.headers["x-cache"] == "HIT"
    assert response.json() == cached_payload


def test_me_returns_db_when_cache_misses(db, clear_dependency_overrides, monkeypatch):
    role = db.query(Role).filter(Role.name == RoleName.USER).one_or_none()
    if not role:
        role = Role(name=RoleName.USER)
        db.add(role)
        db.commit()

    user = User(
        email="miss@itmexicali.edu.mx",
        name="Miss User",
        oauth_provider="google",
        oauth_sub="cache-miss-1",
        id_role=role.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=user.id,
        role=RoleName.USER,
    )
    monkeypatch.setattr(
        "app.routers.auth.users.cache_service.get_json_with_status",
        lambda _key: (None, "miss"),
    )
    monkeypatch.setattr(
        "app.routers.auth.users.cache_service.set_json",
        lambda _key, _value, _ttl: None,
    )

    client = TestClient(app)
    response = client.get("/users/me")

    assert response.status_code == 200
    assert response.headers["x-cache"] == "MISS"
    assert response.json()["id"] == user.id
    assert response.json()["email"] == "miss@itmexicali.edu.mx"


def test_me_returns_db_when_cache_bypassed(db, clear_dependency_overrides, monkeypatch):
    role = db.query(Role).filter(Role.name == RoleName.USER).one_or_none()
    if not role:
        role = Role(name=RoleName.USER)
        db.add(role)
        db.commit()

    user = User(
        email="bypass@itmexicali.edu.mx",
        name="Bypass User",
        oauth_provider="google",
        oauth_sub="cache-bypass-1",
        id_role=role.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=user.id,
        role=RoleName.USER,
    )
    monkeypatch.setattr(
        "app.routers.auth.users.cache_service.get_json_with_status",
        lambda _key: (None, "bypass"),
    )
    monkeypatch.setattr(
        "app.routers.auth.users.cache_service.set_json",
        lambda _key, _value, _ttl: None,
    )

    client = TestClient(app)
    response = client.get("/users/me")

    assert response.status_code == 200
    assert response.headers["x-cache"] == "BYPASS"
    assert response.json()["id"] == user.id


def test_patch_me_updates_name_and_career(db, clear_dependency_overrides):
    role = db.query(Role).filter(Role.name == RoleName.USER).one_or_none()
    if not role:
        role = Role(name=RoleName.USER)
        db.add(role)
        db.commit()

    career = Career(name="Ingeniería Industrial")
    db.add(career)
    db.commit()
    db.refresh(career)

    user = User(
        email="patch@itmexicali.edu.mx",
        name="Patch User",
        oauth_provider="google",
        oauth_sub="patch-user",
        id_role=role.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=user.id,
        role=RoleName.USER,
    )
    client = TestClient(app)

    response = client.patch(
        "/users/me",
        data={"name": "Updated Patch User", "id_career": career.id},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Updated Patch User"
    assert response.json()["career"] == "Ingeniería Industrial"
    assert response.json()["id"] == user.id
    assert response.json()["email"] == "patch@itmexicali.edu.mx"
    assert response.json()["role"] == RoleName.USER


def test_patch_me_returns_404_when_user_does_not_exist(clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=9999,
        role=RoleName.USER,
    )
    client = TestClient(app)

    response = client.patch(
        "/users/me",
        data={"name": "Updated Patch User"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Usuario no encontrado"


def test_patch_me_invalid_career_returns_404(db, clear_dependency_overrides):
    role = db.query(Role).filter(Role.name == RoleName.USER).one_or_none()
    if not role:
        role = Role(name=RoleName.USER)
        db.add(role)
        db.commit()

    user = User(
        email="invalid-career@itmexicali.edu.mx",
        name="Career User",
        oauth_provider="google",
        oauth_sub="invalid-career-user",
        id_role=role.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=user.id,
        role=RoleName.USER,
    )
    client = TestClient(app)

    response = client.patch(
        "/users/me",
        data={"id_career": 9999},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Carrera no encontrada"


def test_patch_me_blank_name_keeps_existing_name(db, clear_dependency_overrides):
    role = db.query(Role).filter(Role.name == RoleName.USER).one_or_none()
    if not role:
        role = Role(name=RoleName.USER)
        db.add(role)
        db.commit()

    user = User(
        email="blank-name@itmexicali.edu.mx",
        name="Stable Name",
        oauth_provider="google",
        oauth_sub="blank-name-user",
        id_role=role.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=user.id,
        role=RoleName.USER,
    )
    client = TestClient(app)

    response = client.patch(
        "/users/me",
        data={"name": "   "},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Stable Name"


def test_patch_me_uploads_first_photo_without_delete(
    db, clear_dependency_overrides, monkeypatch
):
    role = db.query(Role).filter(Role.name == RoleName.USER).one_or_none()
    if not role:
        role = Role(name=RoleName.USER)
        db.add(role)
        db.commit()

    user = User(
        email="first-photo@itmexicali.edu.mx",
        name="First Photo User",
        oauth_provider="google",
        oauth_sub="first-photo-user",
        id_role=role.id,
        photo=None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=user.id,
        role=RoleName.USER,
    )
    client = TestClient(app)

    called = {"deleted": False}

    async def fake_upload_file(file, bucket_name, prefix):
        del file
        assert bucket_name == settings.R2_BUCKET_PUBLIC
        assert prefix == f"users/{user.id}/photo"
        return f"users/{user.id}/photo/new.png"

    async def fake_delete_file(bucket_name, object_key):
        del bucket_name, object_key
        called["deleted"] = True

    monkeypatch.setattr(
        "app.routers.auth.users.storage_service.upload_file",
        fake_upload_file,
    )
    monkeypatch.setattr(
        "app.routers.auth.users.storage_service.delete_file",
        fake_delete_file,
    )

    response = client.patch(
        "/users/me",
        files={"photo": ("new.png", b"fake-image", "image/png")},
    )

    assert response.status_code == 200
    assert called["deleted"] is False


def test_patch_me_invalidates_user_me_cache(
    db, clear_dependency_overrides, monkeypatch
):
    role = db.query(Role).filter(Role.name == RoleName.USER).one_or_none()
    if not role:
        role = Role(name=RoleName.USER)
        db.add(role)
        db.commit()

    user = User(
        email="invalidate@itmexicali.edu.mx",
        name="Invalidate User",
        oauth_provider="google",
        oauth_sub="invalidate-user",
        id_role=role.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=user.id,
        role=RoleName.USER,
    )

    deleted_keys = []
    monkeypatch.setattr(
        "app.routers.auth.users.cache_service.delete",
        lambda key: deleted_keys.append(key),
    )

    client = TestClient(app)
    response = client.patch("/users/me", data={"name": "Updated"})

    assert response.status_code == 200
    assert f"users:me:v1:{user.id}" in deleted_keys
    assert f"auth:user:v1:{user.id}" in deleted_keys


def test_patch_me_uploads_photo_and_deletes_previous_public_image(
    db, clear_dependency_overrides, monkeypatch
):
    role = db.query(Role).filter(Role.name == RoleName.USER).one_or_none()
    if not role:
        role = Role(name=RoleName.USER)
        db.add(role)
        db.commit()

    user = User(
        email="photo@itmexicali.edu.mx",
        name="Photo User",
        oauth_provider="google",
        oauth_sub="photo-user",
        id_role=role.id,
        photo="users/1/photo/old.png",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=user.id,
        role=RoleName.USER,
    )
    client = TestClient(app)

    async def fake_upload_file(file, bucket_name, prefix):
        return "users/1/photo/new.png"

    async def fake_delete_file(bucket_name, object_key):
        assert bucket_name == settings.R2_BUCKET_PUBLIC
        assert object_key == "users/1/photo/old.png"  # stored key, no URL prefix

    monkeypatch.setattr(
        "app.routers.auth.users.storage_service.upload_file",
        fake_upload_file,
    )
    monkeypatch.setattr(
        "app.routers.auth.users.storage_service.delete_file",
        fake_delete_file,
    )

    response = client.patch(
        "/users/me",
        files={"photo": ("new.png", b"fake-image", "image/png")},
    )

    base = (
        settings.R2_PUBLIC_URL or f"{settings.R2_ENDPOINT}/{settings.R2_BUCKET_PUBLIC}"
    ).rstrip("/")
    assert response.status_code == 200
    assert response.json()["photo"] == f"{base}/users/1/photo/new.png"


def test_update_my_career_not_found(db, clear_dependency_overrides):
    role = db.query(Role).filter(Role.name == RoleName.USER).one_or_none()
    if not role:
        role = Role(name=RoleName.USER)
        db.add(role)
        db.commit()

    user = User(
        email="career404@itmexicali.edu.mx",
        name="Career 404",
        oauth_provider="google",
        oauth_sub="career-404",
        id_role=role.id,
    )
    db.add(user)
    db.commit()

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=user.id,
        role=RoleName.USER,
    )
    client = TestClient(app)

    response = client.patch("/users/me/career", json={"career_id": 9999})

    assert response.status_code == 404
    assert response.json()["detail"] == "Carrera no encontrada"


def test_update_my_career_user_not_found(db, clear_dependency_overrides):
    career = Career(name="Ingeniería en Sistemas")
    db.add(career)
    db.commit()
    db.refresh(career)

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=9999,
        role=RoleName.USER,
    )
    client = TestClient(app)

    response = client.patch("/users/me/career", json={"career_id": career.id})

    assert response.status_code == 404
    assert response.json()["detail"] == "Usuario no encontrado"


def test_update_my_career_success(db, clear_dependency_overrides):
    role = db.query(Role).filter(Role.name == RoleName.USER).one_or_none()
    if not role:
        role = Role(name=RoleName.USER)
        db.add(role)
        db.commit()

    career = Career(name="Ingeniería Industrial")
    db.add(career)
    db.flush()

    user = User(
        email="career-ok@itmexicali.edu.mx",
        name="Career Ok",
        oauth_provider="google",
        oauth_sub="career-ok",
        id_role=role.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=user.id,
        role=RoleName.USER,
    )
    client = TestClient(app)

    response = client.patch("/users/me/career", json={"career_id": career.id})

    assert response.status_code == 200
    assert response.json() == {"id_career": career.id}

    db.refresh(user)
    assert user.id_career == career.id


def test_update_my_career_invalidates_user_me_cache(
    db, clear_dependency_overrides, monkeypatch
):
    role = db.query(Role).filter(Role.name == RoleName.USER).one_or_none()
    if not role:
        role = Role(name=RoleName.USER)
        db.add(role)
        db.commit()

    career = Career(name="Ing. Electrónica")
    db.add(career)
    db.flush()

    user = User(
        email="career-invalidate@itmexicali.edu.mx",
        name="Career Invalidate",
        oauth_provider="google",
        oauth_sub="career-invalidate",
        id_role=role.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=user.id,
        role=RoleName.USER,
    )

    deleted_keys = []
    monkeypatch.setattr(
        "app.routers.auth.users.cache_service.delete",
        lambda key: deleted_keys.append(key),
    )

    client = TestClient(app)
    response = client.patch("/users/me/career", json={"career_id": career.id})

    assert response.status_code == 200
    assert f"users:me:v1:{user.id}" in deleted_keys
    assert f"auth:user:v1:{user.id}" in deleted_keys


def test_delete_my_account_anonymizes_user_and_revokes_session(
    db, clear_dependency_overrides, monkeypatch
):
    role = db.query(Role).filter(Role.name == RoleName.USER).one_or_none()
    if not role:
        role = Role(name=RoleName.USER)
        db.add(role)
        db.commit()

    career = Career(name="Ingeniería Mecatrónica")
    db.add(career)
    db.flush()

    user = User(
        email="delete-me@itmexicali.edu.mx",
        name="Delete Me",
        oauth_provider="google",
        oauth_sub="delete-me-user",
        id_role=role.id,
        id_career=career.id,
        photo="users/delete-me/photo.png",
    )
    db.add(user)
    db.flush()

    successor = User(
        email="successor@itmexicali.edu.mx",
        name="Successor",
        oauth_provider="google",
        oauth_sub="successor-user",
        id_role=role.id,
    )
    db.add(successor)
    db.flush()

    transferred_club = Club(
        name="Club con sucesor",
        description="Club que debe transferirse",
        id_leader=user.id,
    )
    archived_club = Club(
        name="Club sin sucesor",
        description="Club que debe archivarse",
        id_leader=user.id,
    )
    db.add_all([transferred_club, archived_club])
    db.flush()
    db.add_all(
        [
            ClubMember(id_club=transferred_club.id, id_user=user.id),
            ClubMember(id_club=transferred_club.id, id_user=successor.id),
            ClubMember(id_club=archived_club.id, id_user=user.id),
            ClubJoinRequest(id_club=transferred_club.id, id_user=user.id),
        ]
    )

    deleted_post = ClubPost(
        content="Contenido que debe eliminarse",
        id_club=transferred_club.id,
        id_author=user.id,
    )
    retained_post = ClubPost(
        content="Contenido de otro usuario",
        id_club=transferred_club.id,
        id_author=successor.id,
    )
    db.add_all([deleted_post, retained_post])
    db.flush()
    db.add_all(
        [
            ClubPostImage(
                id_post=deleted_post.id,
                url="clubs/1/posts/deleted-image.jpg",
            ),
            ClubPostComment(
                id_post=retained_post.id,
                id_user=user.id,
                content="Comentario que debe eliminarse",
            ),
            ClubPostLike(id_post=retained_post.id, id_user=user.id),
            ClubMessage(
                id_club=transferred_club.id,
                id_user=user.id,
                content="Mensaje que debe eliminarse",
            ),
            ClubEvent(
                id_club=transferred_club.id,
                id_author=user.id,
                title="Evento que debe eliminarse",
                date=datetime.now(UTC),
            ),
            UserSession(
                id_user=user.id,
                refresh_token="refresh-token",
                push_token="ExponentPushToken[deleted-user]",
            ),
            Notification(
                id_user=user.id,
                category=NotificationCategory.REPORTS,
                event_type=NotificationEventType.COMPLAINT_SUBMITTED,
                title="Notificación personal",
                body="Debe eliminarse",
            ),
            UserBlock(blocker_id=user.id, blocked_id=successor.id),
        ]
    )

    complaint = Complaint(
        id_user=user.id,
        type=ComplaintType.REPORT,
        title="Queja institucional retenida",
        description="Seguimiento institucional",
        category=ComplaintCategory.SECURITY,
        status=ComplaintStatus.PENDING,
    )
    db.add(complaint)
    db.flush()
    complaint_image = ComplaintImage(
        id_complaint=complaint.id,
        url="complaints/retained/private-image.jpg",
    )
    db.add(complaint_image)
    content_report = ContentReport(
        reporter_id=successor.id,
        reported_user_id=user.id,
        target_type=ContentTargetType.POST,
        target_id=deleted_post.id,
        club_id=transferred_club.id,
        reason=ContentReportReason.OTHER,
        content_snapshot=deleted_post.content,
    )
    db.add(content_report)
    db.commit()
    db.refresh(user)
    deleted_post_id = deleted_post.id
    retained_post_id = retained_post.id
    complaint_id = complaint.id
    complaint_image_id = complaint_image.id
    content_report_id = content_report.id

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=user.id,
        role=RoleName.USER,
    )

    deleted_files = []
    deleted_cache_keys = []

    async def fake_delete_file(bucket_name, object_key):
        deleted_files.append((bucket_name, object_key))

    monkeypatch.setattr(
        "app.routers.auth.users.storage_service.delete_file",
        fake_delete_file,
    )
    monkeypatch.setattr(
        "app.routers.auth.users.cache_service.delete",
        lambda key: deleted_cache_keys.append(key),
    )

    response = TestClient(app).delete("/users/me")

    assert response.status_code == 204
    assert response.content == b""

    db.refresh(user)
    assert user.email.startswith(f"deleted-{user.id}-")
    assert user.email.endswith("@deleted.invalid")
    assert user.oauth_provider == "deleted"
    assert user.oauth_sub not in {"", "delete-me-user"}
    assert user.name == "Cuenta eliminada"
    assert user.photo is None
    assert user.id_career is None
    assert user.is_active is False
    assert db.query(UserSession).filter(UserSession.id_user == user.id).count() == 0
    assert (
        db.query(ClubPost).filter(ClubPost.id == deleted_post_id).one_or_none() is None
    )
    assert (
        db.query(ClubPostImage).filter(ClubPostImage.id_post == deleted_post_id).count()
        == 0
    )
    assert db.get(ClubPost, retained_post_id) is not None
    assert (
        db.query(ClubPostComment).filter(ClubPostComment.id_user == user.id).count()
        == 0
    )
    assert db.query(ClubPostLike).filter(ClubPostLike.id_user == user.id).count() == 0
    assert db.query(ClubMessage).filter(ClubMessage.id_user == user.id).count() == 0
    assert db.query(ClubEvent).filter(ClubEvent.id_author == user.id).count() == 0
    assert db.query(ClubMember).filter(ClubMember.id_user == user.id).count() == 0
    assert (
        db.query(ClubJoinRequest).filter(ClubJoinRequest.id_user == user.id).count()
        == 0
    )
    assert db.query(Notification).filter(Notification.id_user == user.id).count() == 0
    assert (
        db.query(UserBlock)
        .filter((UserBlock.blocker_id == user.id) | (UserBlock.blocked_id == user.id))
        .count()
        == 0
    )

    db.refresh(transferred_club)
    db.refresh(archived_club)
    assert transferred_club.id_leader == successor.id
    assert transferred_club.archived_at is None
    assert archived_club.id_leader == user.id
    assert archived_club.archived_at is not None

    assert db.get(Complaint, complaint_id) is not None
    assert db.get(ComplaintImage, complaint_image_id) is not None
    assert db.get(ContentReport, content_report_id) is not None
    assert deleted_files == [
        (settings.R2_BUCKET_PUBLIC, "users/delete-me/photo.png"),
        (settings.R2_BUCKET_PUBLIC, "clubs/1/posts/deleted-image.jpg"),
    ]
    assert f"users:me:v1:{user.id}" in deleted_cache_keys
    assert f"auth:user:v1:{user.id}" in deleted_cache_keys

    archived_response = TestClient(app).get(f"/clubs/{archived_club.id}")
    assert archived_response.status_code == 404
    archived_join_response = TestClient(app).post(f"/clubs/{archived_club.id}/members")
    assert archived_join_response.status_code == 404


def test_delete_my_account_returns_404_when_user_does_not_exist(
    clear_dependency_overrides,
):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=9999,
        role=RoleName.USER,
    )

    response = TestClient(app).delete("/users/me")

    assert response.status_code == 404
    assert response.json()["detail"] == "Usuario no encontrado"


# ── GET /users ───────────────────────────────────────────────────────────────


def test_get_all_users_returns_list_for_admin(db, clear_dependency_overrides):
    role = db.query(Role).filter(Role.name == RoleName.USER).one_or_none()
    if not role:
        role = Role(name=RoleName.USER)
        db.add(role)
        db.commit()

    user = User(
        email="list-user@itmexicali.edu.mx",
        name="List User",
        oauth_provider="google",
        oauth_sub="list-user-1",
        id_role=role.id,
    )
    db.add(user)
    db.commit()

    app.dependency_overrides[require_admin] = lambda: CurrentUser(
        id=1,
        role=RoleName.ADMIN,
    )
    client = TestClient(app)

    response = client.get("/users")

    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert any(u["email"] == "list-user@itmexicali.edu.mx" for u in response.json())


def test_get_all_users_forbidden_for_non_admin(clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=1,
        role=RoleName.USER,
    )
    client = TestClient(app)

    response = client.get("/users")

    assert response.status_code == 403


def test_admin_endpoint_returns_payload(clear_dependency_overrides):
    app.dependency_overrides[require_admin] = lambda: CurrentUser(
        id=7,
        role=RoleName.ADMIN,
    )
    client = TestClient(app)

    response = client.get("/users/admin")

    assert response.status_code == 200
    assert response.json()["message"] == "admin access"
    assert response.json()["user"]["id"] == 7


def test_staff_endpoint_returns_payload(clear_dependency_overrides):
    from app.core.security import require_staff

    app.dependency_overrides[require_staff] = lambda: CurrentUser(
        id=8,
        role=RoleName.STAFF,
    )
    client = TestClient(app)

    response = client.get("/users/staff")

    assert response.status_code == 200
    assert response.json()["message"] == "staff access"
    assert response.json()["user"]["id"] == 8


# ── PATCH /users/{user_id}/active ────────────────────────────────────────────


def test_set_user_active_deactivate_success(
    db, clear_dependency_overrides, monkeypatch
):
    role = db.query(Role).filter(Role.name == RoleName.USER).one_or_none()
    if not role:
        role = Role(name=RoleName.USER)
        db.add(role)
        db.commit()

    user = User(
        email="deactivate@itmexicali.edu.mx",
        name="Deactivate User",
        oauth_provider="google",
        oauth_sub="deactivate-1",
        id_role=role.id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    app.dependency_overrides[require_admin] = lambda: CurrentUser(
        id=999, role=RoleName.ADMIN
    )
    monkeypatch.setattr(
        "app.routers.auth.users.cache_service.delete", lambda _key: None
    )

    client = TestClient(app)
    response = client.patch(f"/users/{user.id}/active", json={"is_active": False})

    assert response.status_code == 200
    assert response.json() == {"id": user.id, "is_active": False}
    db.refresh(user)
    assert user.is_active is False


def test_set_user_active_activate_success(db, clear_dependency_overrides, monkeypatch):
    role = db.query(Role).filter(Role.name == RoleName.USER).one_or_none()
    if not role:
        role = Role(name=RoleName.USER)
        db.add(role)
        db.commit()

    user = User(
        email="activate@itmexicali.edu.mx",
        name="Activate User",
        oauth_provider="google",
        oauth_sub="activate-1",
        id_role=role.id,
        is_active=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    app.dependency_overrides[require_admin] = lambda: CurrentUser(
        id=999, role=RoleName.ADMIN
    )
    monkeypatch.setattr(
        "app.routers.auth.users.cache_service.delete", lambda _key: None
    )

    client = TestClient(app)
    response = client.patch(f"/users/{user.id}/active", json={"is_active": True})

    assert response.status_code == 200
    assert response.json() == {"id": user.id, "is_active": True}
    db.refresh(user)
    assert user.is_active is True


def test_set_user_active_not_found(clear_dependency_overrides):
    app.dependency_overrides[require_admin] = lambda: CurrentUser(
        id=999, role=RoleName.ADMIN
    )
    client = TestClient(app)
    response = client.patch("/users/9999/active", json={"is_active": False})

    assert response.status_code == 404
    assert response.json()["detail"] == "Usuario no encontrado"


def test_set_user_active_forbidden_for_non_admin(clear_dependency_overrides):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=1, role=RoleName.USER
    )
    client = TestClient(app)
    response = client.patch("/users/1/active", json={"is_active": False})

    assert response.status_code == 403


def test_set_user_active_invalidates_both_cache_keys(
    db, clear_dependency_overrides, monkeypatch
):
    role = db.query(Role).filter(Role.name == RoleName.USER).one_or_none()
    if not role:
        role = Role(name=RoleName.USER)
        db.add(role)
        db.commit()

    user = User(
        email="cache-invalidate-active@itmexicali.edu.mx",
        name="Cache Active User",
        oauth_provider="google",
        oauth_sub="cache-active-1",
        id_role=role.id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    app.dependency_overrides[require_admin] = lambda: CurrentUser(
        id=999, role=RoleName.ADMIN
    )

    deleted_keys = []
    monkeypatch.setattr(
        "app.routers.auth.users.cache_service.delete",
        lambda key: deleted_keys.append(key),
    )

    client = TestClient(app)
    response = client.patch(f"/users/{user.id}/active", json={"is_active": False})

    assert response.status_code == 200
    assert _auth_user_cache_key(user.id) in deleted_keys
    assert f"users:me:v1:{user.id}" in deleted_keys
