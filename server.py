import asyncio
import datetime
import os
import configparser
import sys

from aiohttp.web_exceptions import HTTPClientError
from loguru import logger

from aiohttp import web
import aiofiles


config = configparser.ConfigParser()
config.read("settings.toml")
settings = config["DEFAULT"]

INTERVAL_SECS = 1
CHUNK_SIZE = 1000 * 8  # 100 KB
IMAGES_PATH = settings.get("photo_folder", "test_photos")
LOG_LEVEL = "DEBUG" if settings.getboolean("logging") else "INFO"

# Update logger level
logger.remove()
logger.add(sys.stderr, level=LOG_LEVEL)


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
    logger.debug(f"Process: {archive_process.pid}")
    logger.debug(f"Errors (if any): {await archive_process.stderr.read(n=CHUNK_SIZE)}")

    byte_archive = bytes()
    while True:
        # read process output part by part
        logger.debug("Starting zipping")
        part = await archive_process.stdout.read(n=CHUNK_SIZE)
        if not part:
            logger.debug("Empty part, ending zipping")
            break
        byte_archive += part
        logger.debug(f"Zipping part: {part[:10]}...")
        yield part, archive_process

    # for testing purposes we can save file.
    # with open(folder + ".zip", "wb") as f:
    #     f.write(byte_archive)


async def archivate(request):
    # Get parameter from url
    archive_hash = request.match_info.get("archive_hash", "")

    # Check if path exists
    folder = os.path.join(IMAGES_PATH, archive_hash)
    full_path = os.path.join(os.getcwd(), folder)
    logger.debug(full_path)
    if not os.path.exists(full_path):
        raise HTTPClientError(reason="404", text="No such folder")

    response = web.StreamResponse()

    # File download header
    response.headers[
        "Content-Disposition"
    ] = f'attachment; filename="{archive_hash}.zip"'

    # Send headers =>
    await response.prepare(request)
    # Now we must not change headers

    # Start async streaming bytes
    process_to_terminate = (
        ""  # keep link to have a possibility to kill interrupted process
    )
    try:
        async for part, process in archive(folder):
            process_to_terminate = process
            logger.debug("Sending archive chunk ...")
            await response.write(part)
            if settings.getboolean("use_test_delay"):
                await asyncio.sleep(settings.getint("delay_in_seconds", 1))

    # User pressed cancel button
    except asyncio.CancelledError:
        timestamp = datetime.datetime.now().isoformat()
        logger.debug(f"Interrupted at {timestamp}")
        raise

    # Notify end side that we are done streaming!
    finally:
        try:
            process_to_terminate.kill()
            logger.debug(f"Terminated: {process_to_terminate.pid}")
        except ProcessLookupError:
            logger.debug("Process")
        except AttributeError:
            logger.debug("Attribute error")
        logger.debug(f"Closing connection")
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
