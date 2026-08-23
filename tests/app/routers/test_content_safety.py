from fastapi.testclient import TestClient

from app.core.roles import RoleName
from app.core.security import get_current_user
from app.main import app
from app.models.auth.role import Role
from app.models.auth.user import User
from app.models.club.club import Club
from app.models.club.club_member import ClubMember
from app.models.club.message import ClubMessage
from app.models.club.post import ClubPost
from app.models.club.post_image import ClubPostImage
from app.models.moderation.content_report import ContentReport, ContentReportStatus
from app.schemas.auth.auth import CurrentUser


def _seed_context(db):
    user_role = Role(name=RoleName.USER.value)
    admin_role = Role(name=RoleName.ADMIN.value)
    staff_role = Role(name=RoleName.STAFF.value)
    db.add_all([user_role, admin_role, staff_role])
    db.flush()

    users = [
        User(
            id=1,
            email="reporter@example.com",
            oauth_provider="test",
            oauth_sub="reporter",
            name="Reporter",
            id_role=user_role.id,
        ),
        User(
            id=2,
            email="author@example.com",
            oauth_provider="test",
            oauth_sub="author",
            name="Author",
            id_role=user_role.id,
        ),
        User(
            id=3,
            email="admin@example.com",
            oauth_provider="test",
            oauth_sub="admin",
            name="Admin",
            id_role=admin_role.id,
        ),
        User(
            id=4,
            email="staff@example.com",
            oauth_provider="test",
            oauth_sub="staff",
            name="Staff",
            id_role=staff_role.id,
        ),
    ]
    db.add_all(users)
    db.flush()

    club = Club(name="Safety Club", description="Test", id_leader=1)
    db.add(club)
    db.flush()
    db.add_all(
        [
            ClubMember(id_club=club.id, id_user=1),
            ClubMember(id_club=club.id, id_user=2),
        ]
    )
    post = ClubPost(content="Contenido denunciable", id_club=club.id, id_author=2)
    message = ClubMessage(content="Mensaje denunciable", id_club=club.id, id_user=2)
    db.add_all([post, message])
    db.commit()
    db.refresh(post)
    db.refresh(message)
    return club, post, message


def _authenticate(user_id: int, role: RoleName) -> None:
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=user_id, role=role
    )


def test_user_can_report_post_and_duplicate_is_rejected(db, clear_dependency_overrides):
    _, post, _ = _seed_context(db)
    _authenticate(1, RoleName.USER)
    client = TestClient(app)
    payload = {
        "target_type": "POST",
        "target_id": post.id,
        "reason": "HARASSMENT",
        "details": "Contenido ofensivo",
    }

    response = client.post("/content-safety/reports", json=payload)
    duplicate = client.post("/content-safety/reports", json=payload)

    assert response.status_code == 201
    assert response.json()["status"] == "PENDING"
    assert duplicate.status_code == 409


def test_reported_content_is_hidden_from_reporter(db, clear_dependency_overrides):
    club, post, message = _seed_context(db)
    _authenticate(1, RoleName.USER)
    client = TestClient(app)
    client.post(
        "/content-safety/reports",
        json={
            "target_type": "POST",
            "target_id": post.id,
            "reason": "SPAM",
        },
    )
    client.post(
        "/content-safety/reports",
        json={
            "target_type": "MESSAGE",
            "target_id": message.id,
            "reason": "SPAM",
        },
    )

    posts = client.get(f"/clubs/{club.id}/posts")
    messages = client.get(f"/clubs/{club.id}/messages")

    assert posts.status_code == 200
    assert posts.json() == []
    assert messages.status_code == 200
    assert messages.json() == []


def test_block_and_unblock_user(db, clear_dependency_overrides):
    _seed_context(db)
    _authenticate(1, RoleName.USER)
    client = TestClient(app)

    blocked = client.post("/content-safety/blocks/2")
    listed = client.get("/content-safety/blocks/me")
    unblocked = client.delete("/content-safety/blocks/2")

    assert blocked.status_code == 201
    assert blocked.json()["name"] == "Author"
    assert [item["id"] for item in listed.json()] == [2]
    assert unblocked.status_code == 204
    assert client.get("/content-safety/blocks/me").json() == []


def test_blocked_user_content_is_filtered(db, clear_dependency_overrides):
    club, _, _ = _seed_context(db)
    _authenticate(1, RoleName.USER)
    client = TestClient(app)
    assert client.post("/content-safety/blocks/2").status_code == 201

    assert client.get(f"/clubs/{club.id}/posts").json() == []
    assert client.get(f"/clubs/{club.id}/messages").json() == []


def test_staff_cannot_access_admin_moderation(db, clear_dependency_overrides):
    _seed_context(db)
    _authenticate(4, RoleName.STAFF)

    response = TestClient(app).get("/content-safety/admin/reports")

    assert response.status_code == 403


def test_admin_can_remove_content_and_suspend_author(db, clear_dependency_overrides):
    _, post, _ = _seed_context(db)
    _authenticate(1, RoleName.USER)
    client = TestClient(app)
    created = client.post(
        "/content-safety/reports",
        json={
            "target_type": "POST",
            "target_id": post.id,
            "reason": "VIOLENCE",
        },
    )
    report_id = created.json()["id"]

    _authenticate(3, RoleName.ADMIN)
    response = client.patch(
        f"/content-safety/admin/reports/{report_id}",
        json={
            "status": "RESOLVED",
            "action": "REMOVE_AND_SUSPEND",
            "moderator_comment": "Incumplimiento confirmado",
        },
    )

    db.expire_all()
    report = db.get(ContentReport, report_id)
    author = db.get(User, 2)
    moderated_post = db.get(ClubPost, post.id)
    assert response.status_code == 200
    assert response.json()["action_taken"] == "REMOVE_AND_SUSPEND"
    assert report.status == ContentReportStatus.RESOLVED
    assert moderated_post.is_removed is True
    assert author.is_active is False


def test_admin_report_includes_post_images(db, clear_dependency_overrides):
    _, post, _ = _seed_context(db)
    db.add(ClubPostImage(id_post=post.id, url="clubs/safety/evidence.jpg"))
    db.commit()
    _authenticate(1, RoleName.USER)
    client = TestClient(app)
    created = client.post(
        "/content-safety/reports",
        json={
            "target_type": "POST",
            "target_id": post.id,
            "reason": "SEXUAL_CONTENT",
        },
    )

    _authenticate(3, RoleName.ADMIN)
    response = client.get(f"/content-safety/admin/reports/{created.json()['id']}")

    assert response.status_code == 200
    assert response.json()["content_image_urls"][0].endswith(
        "/clubs/safety/evidence.jpg"
    )


def test_preventive_filter_rejects_disallowed_post(db, clear_dependency_overrides):
    club, _, _ = _seed_context(db)
    _authenticate(1, RoleName.USER)

    response = TestClient(app).post(
        f"/clubs/{club.id}/posts",
        data={"content": "Te voy a matar"},
    )

    assert response.status_code == 422
    assert "normas de la comunidad" in response.json()["detail"]
