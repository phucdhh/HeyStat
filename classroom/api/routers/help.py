"""Help router – Quick Help glossary for reading jamovi output tables."""
from fastapi import APIRouter, Depends

from models import User
from auth.deps import get_current_user
from services.help_content import GLOSSARY

router = APIRouter(tags=["help"])


@router.get("/help/glossary")
async def glossary(current_user: User = Depends(get_current_user)):
    """Statistical terms with the column-name aliases each jamovi table uses."""
    return {"entries": GLOSSARY}
