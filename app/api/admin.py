from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.backup import BackupError, export_backup, restore_backup
from app.database import get_db
from app.queries import person_or_404
from app.service import person_counts, remove_person

router = APIRouter(prefix="/api/admin")


@router.get("/summary")
def admin_summary(db: Session = Depends(get_db)) -> dict:
    return person_counts(db)


@router.get("/export")
def admin_export(db: Session = Depends(get_db)) -> dict:
    return export_backup(db)


@router.post("/import")
def admin_import(payload: dict, db: Session = Depends(get_db)) -> dict:
    try:
        return restore_backup(db, payload)
    except BackupError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/people/{person_id}", status_code=204)
def admin_delete_person(person_id: int, db: Session = Depends(get_db)) -> Response:
    person = person_or_404(db, person_id)
    remove_person(db, person)
    return Response(status_code=204)
