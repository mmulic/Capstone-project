"""Stub routers — endpoints defined, implementation follows in later sprints."""

from fastapi import APIRouter

# These routers have their paths defined for Swagger docs visibility.
# Full implementation comes in Sprints 3-5.

predict_router = APIRouter(prefix="/api", tags=["Predictions"])
results_router = APIRouter(prefix="/api", tags=["Results"])
chat_router = APIRouter(prefix="/api", tags=["Chatbot"])
evaluate_router = APIRouter(prefix="/api", tags=["Evaluation"])
auth_router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@predict_router.post("/predict", summary="Trigger VLM damage prediction")
async def predict():
    return {"status": "not_implemented", "sprint": 3, "message": "Prediction endpoint — Sprint 3"}


@results_router.get("/results", summary="Query damage assessment results")
async def get_results():
    return {"status": "not_implemented", "sprint": 3, "message": "Results query — Sprint 3"}


@results_router.get("/properties/{property_id}", summary="Get property detail")
async def get_property(property_id: str):
    return {"status": "not_implemented", "sprint": 3, "message": "Property detail — Sprint 3"}


@results_router.get("/stats", summary="Dashboard summary statistics")
async def get_stats():
    return {"status": "not_implemented", "sprint": 4, "message": "Stats endpoint — Sprint 4"}


@chat_router.post("/chat", summary="Chatbot query")
async def chat():
    return {"status": "not_implemented", "sprint": 4, "message": "Chat endpoint — Sprint 4"}


@evaluate_router.get("/evaluate", summary="Evaluate predictions vs FEMA ground truth")
async def evaluate():
    return {"status": "not_implemented", "sprint": 5, "message": "Evaluation — Sprint 5"}


@auth_router.post("/register", summary="Register new user")
async def register():
    return {"status": "not_implemented", "sprint": 5, "message": "Registration — Sprint 5"}


@auth_router.post("/login", summary="Login and get JWT")
async def login():
    return {"status": "not_implemented", "sprint": 5, "message": "Login — Sprint 5"}
