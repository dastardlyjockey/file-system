from fastapi import FastAPI, HTTPException, Depends, File, UploadFile, Form
from .models import Post
from .database import create_db_and_tables, get_sync_session
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager
from sqlalchemy import select
from .images.images import imagekit
import os
import shutil
import uuid
import tempfile


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan)


@app.post("/upload")
async def upload_file(
        file: UploadFile = File(...),
        caption: str = Form(""),
        db: AsyncSession = Depends(get_sync_session)
):
    temp_file_path = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_file:
            temp_file_path = temp_file.name
            shutil.copyfileobj(file.file, temp_file)

        with open(temp_file_path, "rb") as f:
            upload_result = imagekit.files.upload(
                file=f,
                file_name=file.filename,
                folder="/file-system",
                tags=["backend-upload"]
            )

        if upload_result.url:
            post = Post(
                caption=caption,
                url=upload_result.url,
                file_name=upload_result.name,
                file_type="video" if file.content_type.startswith("video/") else "image"
            )

            db.add(post)
            await db.commit()
            await db.refresh(post)

            return post

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)

        file.file.close()


@app.get("/feed")
async def get_feed(db: AsyncSession = Depends(get_sync_session)):
    result = await db.execute(select(Post).order_by(Post.created_at.desc()))
    posts = [row[0] for row in result.all()]

    posts_data = []
    for post in posts:
        posts_data.append(
            {
                "id": str(post.id),
                "caption": post.caption,
                "url": post.url,
                "file_name": post.file_name,
                "file_type": post.file_type,
                "created_at": post.created_at
            }
        )

    return {"Posts": posts_data}
