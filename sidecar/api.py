import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import cv2
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlmodel import Session as DbSession
from sqlmodel import select

from sidecar.camera import CameraWorker, ClipConfig
from sidecar.db import engine, get_session, run_migrations
from sidecar.frame_source import probe_cameras
from sidecar.models import (
    CameraInfo,
    Clip,
    ClipStart,
    FlagSet,
    Frame,
    LabelSet,
    NotesSet,
    Run,
    RunCreate,
    Sample,
    SampleCreate,
    Session,
    SessionCreate,
    Settings,
    SettingsUpdate,
    Snapshot,
    Track,
    TrackRead,
)
from sidecar.paths import get_sessions_dir
from sidecar.settings_service import get_settings, update_settings

PREVIEW_HZ = 15
PREVIEW_PNG_COMPRESSION = 1


def create_app() -> FastAPI:
    worker = CameraWorker(engine)
    # Cache: sample_id -> currently-open run_id. Survives the app's lifetime.
    active_run_for_sample: dict[int, int] = {}

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        # Apply any pending schema changes BEFORE touching settings/etc.
        run_migrations()
        # Materialise settings so the cache and ImageProcessor are populated
        # before the capture loop starts pulling frames.
        get_settings()
        worker.start_capture()
        try:
            yield
        finally:
            worker.stop()

    app = FastAPI(title="Microorganism Classifier Sidecar", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthz")
    def healthz() -> dict:
        return {
            "ok": True,
            "capturing": worker.is_capturing,
            "clipping": worker.is_clipping,
        }

    @app.get("/settings", response_model=Settings)
    def read_settings() -> Settings:
        return get_settings()

    @app.patch("/settings", response_model=Settings)
    def patch_settings(payload: SettingsUpdate) -> Settings:
        if payload.data_dir is not None:
            p = Path(payload.data_dir).expanduser()
            try:
                p.mkdir(parents=True, exist_ok=True)
            except OSError as err:
                raise HTTPException(400, f"cannot create directory: {err}") from err
            payload.data_dir = str(p.resolve())
        previous_device = get_settings().device_index
        updated = update_settings(**payload.model_dump(exclude_unset=True))
        if updated.device_index != previous_device:
            worker.request_reload()
        return updated

    @app.get("/cameras", response_model=list[CameraInfo])
    def list_cameras() -> list[CameraInfo]:
        return [
            CameraInfo(index=i, name=name, width=w, height=h)
            for i, name, w, h in probe_cameras()
        ]

    @app.post("/sessions", response_model=Session)
    def create_session(payload: SessionCreate, db: DbSession = Depends(get_session)) -> Session:
        sess = Session.model_validate(payload)
        db.add(sess)
        db.commit()
        db.refresh(sess)
        return sess

    @app.get("/sessions", response_model=list[Session])
    def list_sessions(db: DbSession = Depends(get_session)) -> list[Session]:
        return list(db.exec(select(Session).order_by(Session.id.desc()).limit(100)).all())

    @app.post("/samples", response_model=Sample)
    def create_sample(payload: SampleCreate, db: DbSession = Depends(get_session)) -> Sample:
        sample = Sample.model_validate(payload)
        db.add(sample)
        db.commit()
        db.refresh(sample)
        return sample

    @app.post("/runs", response_model=Run)
    def create_run(payload: RunCreate, db: DbSession = Depends(get_session)) -> Run:
        run = Run.model_validate(payload)
        db.add(run)
        db.commit()
        db.refresh(run)
        return run

    def _ensure_run(sample_id: int, db: DbSession) -> Run:
        """Find an open run for this sample, or create a new one."""
        cached = active_run_for_sample.get(sample_id)
        if cached is not None:
            run = db.get(Run, cached)
            if run is not None and run.ended_at is None:
                return run
        existing = db.exec(
            select(Run).where(Run.sample_id == sample_id, Run.ended_at.is_(None))
        ).first()
        if existing is not None:
            active_run_for_sample[sample_id] = existing.id
            return existing
        run = Run(sample_id=sample_id)
        db.add(run)
        db.commit()
        db.refresh(run)
        active_run_for_sample[sample_id] = run.id
        return run

    @app.post("/clips/start", response_model=Clip)
    def start_clip(payload: ClipStart, db: DbSession = Depends(get_session)) -> Clip:
        if worker.is_clipping:
            raise HTTPException(409, "a clip is already being recorded")
        sample = db.get(Sample, payload.sample_id)
        if sample is None:
            raise HTTPException(404, "sample not found")
        run = _ensure_run(payload.sample_id, db)

        clip_dir = (
            get_sessions_dir() / f"session_{sample.session_id:06d}" / f"run_{run.id:06d}" / "clips"
        )
        clip_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(UTC)
        clip_path = clip_dir / f"clip_{ts.strftime('%Y%m%d_%H%M%S')}.mp4"

        clip = Clip(
            run_id=run.id,
            started_at=ts,
            path=str(clip_path),
            seconds_before=payload.seconds_before,
        )
        db.add(clip)
        db.commit()
        db.refresh(clip)

        try:
            worker.start_clip(
                ClipConfig(
                    clip_id=clip.id,
                    run_id=run.id,
                    clip_dir=clip_dir,
                    clip_path=clip_path,
                    seconds_before=payload.seconds_before,
                )
            )
        except RuntimeError as err:
            raise HTTPException(409, str(err)) from err
        return clip

    @app.post("/clips/stop", response_model=Clip)
    def stop_clip(db: DbSession = Depends(get_session)) -> Clip:
        cfg = worker.current_clip
        if cfg is None:
            raise HTTPException(409, "no clip is being recorded")
        clip_id = cfg.clip_id
        worker.stop_clip()
        clip = db.get(Clip, clip_id)
        if clip is None:
            raise HTTPException(404, "clip vanished")
        db.refresh(clip)
        return clip

    @app.get("/clips", response_model=list[Clip])
    def list_clips(
        run_id: int | None = None,
        flagged: bool | None = None,
        label: str | None = None,
        limit: int = 200,
        db: DbSession = Depends(get_session),
    ) -> list[Clip]:
        stmt = select(Clip)
        if run_id is not None:
            stmt = stmt.where(Clip.run_id == run_id)
        if flagged is not None:
            stmt = stmt.where(Clip.flagged == flagged)
        if label is not None:
            stmt = stmt.where(Clip.label == label)
        stmt = stmt.order_by(Clip.id.desc()).limit(limit)
        return list(db.exec(stmt).all())

    @app.post("/clips/{clip_id}/label")
    def label_clip(clip_id: int, payload: LabelSet, db: DbSession = Depends(get_session)) -> dict:
        clip = db.get(Clip, clip_id)
        if clip is None:
            raise HTTPException(404, "clip not found")
        clip.label = payload.label
        db.add(clip)
        db.commit()
        return {"ok": True}

    @app.post("/clips/{clip_id}/flag")
    def flag_clip(clip_id: int, payload: FlagSet, db: DbSession = Depends(get_session)) -> dict:
        clip = db.get(Clip, clip_id)
        if clip is None:
            raise HTTPException(404, "clip not found")
        clip.flagged = payload.flagged
        db.add(clip)
        db.commit()
        return {"ok": True}

    @app.get("/tracks", response_model=list[Track])
    def list_tracks(
        run_id: int | None = None,
        session_id: int | None = None,
        flagged: bool | None = None,
        label: str | None = None,
        min_area: float | None = None,
        sort: str = "id_desc",
        limit: int = 200,
        db: DbSession = Depends(get_session),
    ) -> list[Track]:
        stmt = select(Track)
        if run_id is not None:
            stmt = stmt.where(Track.run_id == run_id)
        if session_id is not None:
            stmt = (
                stmt.join(Run, Track.run_id == Run.id)
                .join(Sample, Run.sample_id == Sample.id)
                .where(Sample.session_id == session_id)
            )
        if flagged is not None:
            stmt = stmt.where(Track.flagged == flagged)
        if label is not None:
            stmt = stmt.where(Track.label == label)
        if min_area is not None:
            stmt = stmt.where(Track.mean_area_px >= min_area)

        if sort == "area_desc":
            stmt = stmt.order_by(Track.mean_area_px.desc())
        elif sort == "duration_desc":
            stmt = stmt.order_by((Track.end_video_ms - Track.start_video_ms).desc())
        else:
            stmt = stmt.order_by(Track.id.desc())

        return list(db.exec(stmt.limit(limit)).all())

    @app.get("/tracks/{track_id}", response_model=TrackRead)
    def get_track(track_id: int, db: DbSession = Depends(get_session)) -> TrackRead:
        track = db.get(Track, track_id)
        if track is None:
            raise HTTPException(404, "track not found")
        frames = list(
            db.exec(
                select(Frame).where(Frame.track_id == track_id).order_by(Frame.sharpness.desc())
            ).all()
        )
        clip = db.exec(
            select(Clip).where(Clip.run_id == track.run_id).order_by(Clip.id.desc())
        ).first()
        return TrackRead(
            **track.model_dump(),
            frames=frames,
            recording=None,
            clip=clip,
        )

    @app.post("/tracks/{track_id}/label")
    def label_track(track_id: int, payload: LabelSet, db: DbSession = Depends(get_session)) -> dict:
        track = db.get(Track, track_id)
        if track is None:
            raise HTTPException(404, "track not found")
        worker.set_label(track_id, payload.label)
        return {"ok": True}

    @app.post("/tracks/{track_id}/flag")
    def flag_track(track_id: int, payload: FlagSet, db: DbSession = Depends(get_session)) -> dict:
        track = db.get(Track, track_id)
        if track is None:
            raise HTTPException(404, "track not found")
        track.flagged = payload.flagged
        db.add(track)
        db.commit()
        return {"ok": True}

    @app.post("/tracks/{track_id}/notes")
    def notes_track(track_id: int, payload: NotesSet, db: DbSession = Depends(get_session)) -> dict:
        track = db.get(Track, track_id)
        if track is None:
            raise HTTPException(404, "track not found")
        track.notes = payload.notes
        db.add(track)
        db.commit()
        return {"ok": True}

    @app.post("/snapshots", response_model=Snapshot)
    def create_snapshot(payload: ClipStart, db: DbSession = Depends(get_session)) -> Snapshot:
        snap = worker.snapshot()
        if snap.frame is None:
            raise HTTPException(409, "no frame available yet")
        sample = db.get(Sample, payload.sample_id)
        if sample is None:
            raise HTTPException(404, "sample not found")
        run = _ensure_run(payload.sample_id, db)

        out_dir = (
            get_sessions_dir()
            / f"session_{sample.session_id:06d}"
            / f"run_{run.id:06d}"
            / "snapshots"
        )
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(UTC)
        path = out_dir / f"{ts.strftime('%Y%m%d_%H%M%S_%f')}.png"
        cv2.imwrite(str(path), snap.frame)
        snapshot = Snapshot(run_id=run.id, ts=ts, path=str(path))
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)
        return snapshot

    @app.get("/snapshots", response_model=list[Snapshot])
    def list_snapshots(
        run_id: int | None = None,
        flagged: bool | None = None,
        label: str | None = None,
        limit: int = 200,
        db: DbSession = Depends(get_session),
    ) -> list[Snapshot]:
        stmt = select(Snapshot)
        if run_id is not None:
            stmt = stmt.where(Snapshot.run_id == run_id)
        if flagged is not None:
            stmt = stmt.where(Snapshot.flagged == flagged)
        if label is not None:
            stmt = stmt.where(Snapshot.label == label)
        stmt = stmt.order_by(Snapshot.id.desc()).limit(limit)
        return list(db.exec(stmt).all())

    @app.post("/snapshots/{snap_id}/label")
    def label_snapshot(
        snap_id: int, payload: LabelSet, db: DbSession = Depends(get_session)
    ) -> dict:
        snap = db.get(Snapshot, snap_id)
        if snap is None:
            raise HTTPException(404, "snapshot not found")
        snap.label = payload.label
        db.add(snap)
        db.commit()
        return {"ok": True}

    @app.post("/snapshots/{snap_id}/flag")
    def flag_snapshot(snap_id: int, payload: FlagSet, db: DbSession = Depends(get_session)) -> dict:
        snap = db.get(Snapshot, snap_id)
        if snap is None:
            raise HTTPException(404, "snapshot not found")
        snap.flagged = payload.flagged
        db.add(snap)
        db.commit()
        return {"ok": True}

    @app.get("/file")
    def serve_file(path: str):
        p = Path(path).resolve()
        if not p.is_file():
            raise HTTPException(404, "not found")
        # Allow anything inside the user's home directory. Historical paths
        # from a previous data_dir keep working when the directory is changed.
        try:
            p.relative_to(Path.home().resolve())
        except ValueError as err:
            raise HTTPException(403, "outside home directory") from err
        return FileResponse(p)

    @app.websocket("/ws/preview")
    async def ws_preview(ws: WebSocket) -> None:
        await ws.accept()
        last_frame_index = -1
        try:
            while True:
                snap = worker.snapshot()
                payload: dict = {
                    "frame_index": snap.frame_index,
                    "saved_tracks": snap.saved_tracks,
                    "tracks": snap.tracks,
                    "clipping": worker.is_clipping,
                }
                if snap.frame is not None and snap.frame_index != last_frame_index:
                    # PNG is lossless, so the browser sees the exact processed frame pixels.
                    ok, buf = cv2.imencode(
                        ".png",
                        snap.frame,
                        [int(cv2.IMWRITE_PNG_COMPRESSION), PREVIEW_PNG_COMPRESSION],
                    )
                    if ok:
                        await ws.send_bytes(bytes(buf))
                        last_frame_index = snap.frame_index
                await ws.send_json(payload)
                await asyncio.sleep(1.0 / PREVIEW_HZ)
        except WebSocketDisconnect:
            return

    return app
