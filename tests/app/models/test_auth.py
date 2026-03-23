from app.models.auth import Role


def test_create_role(db):
    role = Role(name="admin")
    db.add(role)
    db.commit()
    db.refresh(role)

    assert role.id is not None
    assert role.name == "admin"
