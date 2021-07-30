import asyncio
import os
from loguru import logger

from aiohttp import web
import aiofiles

INTERVAL_SECS = 1
CHUNK_SIZE = 1000 * 8  # 100 KB
IMAGES_PATH = "test_photos/"


async def archive(folder):
    """Archive the folder asynchronously."""
    # flag "-" helps to redirect output bytes to stdout
    # flag "-j" do not include parent directory in archive
    command = f"zip -r -j - {folder}"
    archive_process = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,  # catch archive bytes from stdout
        stderr=asyncio.subprocess.PIPE,
    )

    byte_archive = bytes()
    while True:
        # read process output part by part
        part = await archive_process.stdout.read(n=CHUNK_SIZE)
        if not part:
            break
        byte_archive += part
        yield part

    # for testing purposes we can save file.
    # with open(folder + ".zip", "wb") as f:
    #     f.write(byte_archive)


async def archivate(request):
    # Get parameter from url
    archive_hash = request.match_info.get("archive_hash", "")

    # Check if path exists
    folder = IMAGES_PATH + archive_hash
    full_path = os.path.join(os.getcwd(), folder)
    logger.debug(full_path)
    if not os.path.exists(full_path):
        return web.Response(text="Archive was deleted, sorry.")

    response = web.StreamResponse()

    # File download header
    response.headers[
        "Content-Disposition"
    ] = f'attachment; filename="{archive_hash}.zip"'

    # Send headers =>
    await response.prepare(request)
    # Now we must not change headers

    # Start async streaming bytes
    async for part in archive(folder):
        await response.write(part)

    # Notify end side that we are done streaming!
    await response.write_eof()


async def handle_index_page(request):
    async with aiofiles.open("index.html", mode="r") as index_file:
        index_contents = await index_file.read()
    return web.Response(text=index_contents, content_type="text/html")


if __name__ == "__main__":
    app = web.Application()
    app.add_routes(
        [
            web.get("/", handle_index_page),
            web.get("/archive/{archive_hash}/", archivate),
        ]
    )
    web.run_app(app)
