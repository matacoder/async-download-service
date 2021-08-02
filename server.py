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


async def make_archive(archive_hash, full_path):
    """Archive the folder asynchronously."""
    zip_cmd = [
        "zip",
        "-r",
        "-",
        ".",
    ]

    archive_process = await asyncio.create_subprocess_exec(
        *zip_cmd,
        cwd=full_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    logger.debug(f"Process: {archive_process.pid}")
    logger.debug(
        f"Errors (if any): {await archive_process.stderr.read(n=settings.getint('chunk_size'))}"
    )

    byte_archive = bytes()
    while True:
        logger.debug("Starting zipping")
        part = await archive_process.stdout.read(n=settings.getint("chunk_size"))
        if not part:
            logger.debug("Empty part, ending zipping")
            break
        byte_archive += part
        logger.debug(f"Zipping part: {part[:10]}...")
        yield part, archive_process


async def stream_archive(request):
    """Streaming data to user."""
    archive_hash = request.match_info["archive_hash"]

    full_path = os.path.join(os.getcwd(), settings.get("photo_folder"), archive_hash)
    logger.debug(full_path)
    if not os.path.exists(full_path):
        raise HTTPClientError(reason="404", text="No such folder")

    response = web.StreamResponse()
    response.enable_chunked_encoding()

    response.headers[
        "Content-Disposition"
    ] = f'attachment; filename="{archive_hash}.zip"'

    await response.prepare(request)

    process_to_terminate = ""

    try:
        async for part, process in make_archive(archive_hash, full_path):
            process_to_terminate = process
            logger.debug("Sending archive chunk ...")
            await response.write(part)
            if settings.getboolean("use_test_delay"):
                await asyncio.sleep(settings.getint("delay_in_seconds"))

    except asyncio.CancelledError:
        timestamp = datetime.datetime.now().isoformat()
        logger.debug(f"Interrupted at {timestamp}")
        raise

    finally:
        try:
            process_to_terminate.kill()
            logger.debug(f"Terminated: {process_to_terminate.pid}")
        except ProcessLookupError:
            logger.debug("Process not found.")
        except AttributeError:
            logger.debug("Attribute error (check create_subprocess_shell errors PIPE)")
        logger.debug(f"Closing connection")
        await response.write_eof()


async def handle_index_page(request):
    async with aiofiles.open("index.html", mode="r") as index_file:
        index_contents = await index_file.read()
    return web.Response(text=index_contents, content_type="text/html")


if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stderr, level=settings["logger_level"])

    app = web.Application()
    app.add_routes(
        [
            web.get("/", handle_index_page),
            web.get("/archive/{archive_hash}/", stream_archive),
        ]
    )
    web.run_app(app)
