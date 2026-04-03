from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
# Asegúrate de que las rutas a tus modelos sean las correctas:
from app.models.auth.user import User
from app.models.complaint import Complaint, ComplaintStatus
from app.models.complaint.complaint_evidence import ComplaintEvidence
from app.models.complaint.complaint_status_history import ComplaintStatusHistory
from app.schemas.complaint import ComplaintOut, ComplaintStatusUpdate
from app.services.storage_service import storage_service

router = APIRouter(prefix="/complaints", tags=["Complaints (Staff)"])

# --- Dependencia / Utilidad para verificar que es Staff ---
def require_staff_role(current_user: User = Depends(get_current_user)):
    # Ajusta esta validación según cómo se llame tu rol en la BD
    if current_user.role.name not in ["staff", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado. Se requieren permisos de Staff o Administrador."
        )
    return current_user


# 1. GET /complaints: Ver todas las quejas (solo Staff/Admin)
@router.get("", response_model=list[ComplaintOut])
def get_all_complaints(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_role)
):
    """Obtiene el listado de todas las quejas registradas."""
    complaints = db.query(Complaint).order_by(Complaint.created_at.desc()).all()
    return complaints


@router.post("/{complaint_id}/evidence")
async def upload_complaint_evidence(
    complaint_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_role) # 🔒 1. SEGURIDAD ACTIVADA DE NUEVO
):
    """Sube un archivo de evidencia al bucket privado y lo enlaza a la queja."""
    
    # 🗄️ 2. VALIDACIÓN DE BASE DE DATOS ACTIVADA
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Queja no encontrada")

    # Configuración de R2
    bucket_name = "dev-agora-private"
    prefix = f"complaints/{complaint_id}/evidence"
    
    # ☁️ 3. SUBIDA A CLOUDFLARE (¡Que ya sabemos que funciona!)
    object_key = await storage_service.upload_file(
        file=file, bucket_name=bucket_name, prefix=prefix
    )

    # 💾 4. GUARDADO EN BASE DE DATOS ACTIVADO
    new_evidence = ComplaintEvidence(
        id_complaint=complaint_id,
        id_user=current_user.id,  # Usa el ID del Staff real
        url=object_key            
    )
    db.add(new_evidence)
    db.commit()

    return {"message": "Evidencia subida y guardada exitosamente", "object_key": object_key}


# 3. PATCH /complaints/{id}/status: Cambiar el estado de la queja
@router.patch("/{complaint_id}/status")
def update_complaint_status(
    complaint_id: int,
    status_update: ComplaintStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_role)
):
    """
    Actualiza el estado de una queja. 
    Regla estricta: No se puede pasar a RESOLVED sin evidencias.
    """
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Queja no encontrada")

    # VALIDACIÓN: Si la quieren marcar como resuelta, obligar a tener evidencia
    if status_update.status == ComplaintStatus.RESOLVED:
        if not complaint.evidences:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede resolver una queja sin antes subir una evidencia."
            )

    # Actualizamos el estado
    old_status = complaint.status
    complaint.status = status_update.status

    # (Opcional pero muy recomendado) Guardamos el historial del cambio
    status_history = ComplaintStatusHistory(
        complaint_id=complaint.id,
        old_status=old_status,
        new_status=status_update.status,
        changed_by_user_id=current_user.id
    )
    db.add(status_history)
    db.commit()

    return {"message": "Estado actualizado exitosamente", "new_status": complaint.status}