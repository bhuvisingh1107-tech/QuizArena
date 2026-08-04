#!/usr/bin/env python3
"""Trace a media_files id against DB + local storage (Render Shell friendly).

Usage (Render Shell or local with prod DATABASE_URL / STORAGE_PATH):

  cd /app   # or backend/
  python -m scripts.diagnose_media dabc1f65-28ad-4515-ba24-3daac8959c16
"""

from __future__ import annotations

import sys
from uuid import UUID

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.media_file import MediaFile
from app.models.question import Question
from app.models.session_question import SessionQuestion
from app.storage import create_storage_backend


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python -m scripts.diagnose_media <media_uuid>", file=sys.stderr)
        return 2

    media_id = UUID(sys.argv[1])
    settings = get_settings()
    engine = create_engine(settings.database_url)
    backend = create_storage_backend(settings)

    print(f"DATABASE_URL host/db: {engine.url.host}/{engine.url.database}")
    print(f"STORAGE_PATH: {settings.storage_path}")
    print(f"media_id: {media_id}")
    print("---")

    with Session(engine) as session:
        media = session.get(MediaFile, media_id)
        q_ids = [
            str(r[0])
            for r in session.query(Question.id).filter(Question.media_file_id == media_id)
        ]
        sq_ids = [
            str(r[0])
            for r in session.query(SessionQuestion.id).filter(
                SessionQuestion.media_file_id == media_id
            )
        ]

        if media is None:
            print("DB: NO media_files row")
            print(f"questions refs: {len(q_ids)}")
            print(f"session_questions refs: {len(sq_ids)}")
            print("404 source if requested: MediaService.get → MEDIA_NOT_FOUND")
            return 1

        print("DB row:")
        print(f"  id: {media.id}")
        print(f"  storage_key: {media.storage_key}")
        print(f"  mime_type: {media.mime_type}")
        print(f"  file_size: {media.file_size}")
        print(f"  original_filename: {media.original_filename}")
        print(f"  quiz_id: {media.quiz_id}")
        print(f"  created_at: {media.created_at}")

        exists = backend.exists(media.storage_key)
        print(f"file exists: {exists}")
        if exists:
            data = backend.read(media.storage_key)
            print(f"file size bytes: {len(data)}")
            print("Expected content endpoint: 200 (if auth allows)")
            rc = 0
        else:
            print(
                "404 source: LocalStorageBackend.read → MEDIA_BLOB_MISSING "
                "(DB row exists, blob missing under STORAGE_PATH)"
            )
            print(
                "Fix: confirm Render disk mounted at /app/storage, then re-upload "
                "the image and re-apply / start a new live room."
            )
            rc = 1

        print(f"questions using this media ({len(q_ids)}): {q_ids[:10]}")
        print(f"session_questions using this media ({len(sq_ids)}): {sq_ids[:10]}")
        return rc


if __name__ == "__main__":
    raise SystemExit(main())
