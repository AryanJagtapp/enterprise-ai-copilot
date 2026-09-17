from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.db import get_db
from app.prompts.registry import PromptNotFound, PromptRegistry

router = APIRouter(prefix="/prompts", tags=["prompts"])


class CreatePromptVersionRequest(BaseModel):
    prompt_id: str
    description: str
    template: str
    activate: bool = False


@router.get("")
def list_prompts(prompt_id: str | None = None, db: Session = Depends(get_db)):
    registry = PromptRegistry(db)
    return [v.__dict__ for v in registry.list_versions(prompt_id)]


@router.post("")
def create_prompt_version(payload: CreatePromptVersionRequest, db: Session = Depends(get_db)):
    registry = PromptRegistry(db)
    view = registry.create_version(
        payload.prompt_id,
        description=payload.description,
        template=payload.template,
        activate=payload.activate,
    )
    return view.__dict__


@router.post("/{prompt_id}/activate")
def activate_prompt(prompt_id: str, version: int, db: Session = Depends(get_db)):
    registry = PromptRegistry(db)
    try:
        view = registry.activate_version(prompt_id, version)
    except PromptNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return view.__dict__


@router.post("/{prompt_id}/rollback")
def rollback_prompt(prompt_id: str, version: int, db: Session = Depends(get_db)):
    registry = PromptRegistry(db)
    try:
        view = registry.rollback(prompt_id, version)
    except PromptNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return view.__dict__
