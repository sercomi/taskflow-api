import pytest
from app.schemas.project import ProjectUpdate
from pydantic import ValidationError


def test_project_update_accepts_name() -> None:
    update = ProjectUpdate(name="New project name")
    assert update.name == "New project name"


def test_project_update_accepts_description() -> None:
    update = ProjectUpdate(description="Updated description")
    assert update.description == "Updated description"


def test_project_update_allows_clearing_description() -> None:
    update = ProjectUpdate(description=None)

    assert update.description is None
    assert "description" in update.model_fields_set


def test_project_update_rejects_null_name() -> None:
    with pytest.raises(ValidationError):
        ProjectUpdate(name=None)


def test_project_update_rejects_empty_payload() -> None:
    with pytest.raises(ValidationError):
        ProjectUpdate()


def test_project_update_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        ProjectUpdate(unknown="value")  # type: ignore[call-arg]
