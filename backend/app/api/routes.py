from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.models import ManualPhaseRequest, Phase, SystemCommandResponse


router = APIRouter(prefix="/api")


@router.get("/system")
async def system(request: Request):
    return (await request.app.state.store.snapshot()).model_dump(mode="json")


@router.get("/traffic")
async def traffic(request: Request):
    state = await request.app.state.store.snapshot()
    return {k.value: v.model_dump(mode="json") for k, v in state.traffic.items()}


@router.get("/signals")
async def signals(request: Request):
    state = await request.app.state.store.snapshot()
    return {
        "phase": state.phase,
        "remaining": state.remaining,
        "signals": state.signals,
    }


@router.get("/history")
async def history(request: Request, limit: int = Query(120, ge=1, le=600)):
    return request.app.state.store.history(limit)


@router.post("/system/start", response_model=SystemCommandResponse)
async def start(request: Request):
    await request.app.state.store.patch(running=True)
    return SystemCommandResponse(ok=True, message="Adaptive controller started")


@router.post("/system/stop", response_model=SystemCommandResponse)
async def stop(request: Request):
    await request.app.state.store.patch(running=False)
    return SystemCommandResponse(ok=True, message="Stopping safely through yellow/all-red")


@router.post("/manual/phase", response_model=SystemCommandResponse)
async def manual_phase(command: ManualPhaseRequest, request: Request):
    if command.phase not in (Phase.NS_GREEN, Phase.EW_GREEN):
        raise HTTPException(400, "Manual control accepts NS_GREEN or EW_GREEN only")
    state = await request.app.state.store.snapshot()
    if not state.running:
        raise HTTPException(409, "Start the controller before using manual phase control")
    await request.app.state.controller.request_manual(command.phase, command.duration)
    return SystemCommandResponse(ok=True, message=f"Queued safe transition to {command.phase}")


@router.get("/video.mjpg")
async def video(request: Request):
    if request.app.state.vision.mode != "yolo":
        raise HTTPException(404, "Video stream is available only in YOLO mode")
    return StreamingResponse(
        request.app.state.vision.mjpeg(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )

