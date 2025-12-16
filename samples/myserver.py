import time
import json
import asyncio
import userver

GLOBALS = {"debug": 0, "shutdown": 0}
DB = {}


def my_post_handler(url, data):
    code, hdrs = 404, {}

    print("RECEIVED A POST! with data: ", data)
    d = json.loads(data)

    if url == "/users":
        for k, v in d.items():
            DB[k] = v
        code = 200

    return code, "", hdrs


def my_get_handler(url, data):
    code, hdrs = 200, {}
    base, _, remainder = url.rpartition("/")

    def users_fun(_):
        txt = json.dumps(DB)
        print(txt)
        return 200, txt, {"content_type": "application/json"}

    def services_fun(svc_name):
        txt = json.dumps(GLOBALS.get(svc_name))
        return 200, txt, {"content_type": "application/json"}

    def uptime_fun(_):
        with open("/proc/uptime") as f:
            txt = f.readline()
        return 200, txt, {}

    fmap = {"/users": users_fun, "/services": services_fun, "/uptime": uptime_fun}

    f = fmap.get(url.strip())
    if f:
        return f(remainder)
    else:
        return 404, "", {}


def my_patch_handler(url, data):
    if url == "/services":
        print("OLD globals: ", GLOBALS)
        for k, v in data.items():
            if k in GLOBALS:
                GLOBALS[k] = v  # update
        print("NEW globals: ", GLOBALS)
        code = 204

    else:
        code = 404

    return code, "", {}


def my_head_handler(url, data):
    return 200, "nothing", {}


def my_delete_handler(url, data):
    base, _, remainder = url.rpartition("/")
    svc_name = remainder
    if svc_name not in GLOBALS.keys():
        return 404, "", {}
    else:
        del GLOBALS[svc_name]
        return 200, "deleted resource.", {}


async def my_handle_client(reader, writer):
    handlers = {
        "get": my_get_handler,
        "patch": my_patch_handler,
        "post": my_post_handler,
        "head": my_head_handler,
        "delete": my_delete_handler,
    }
    print("New client connected...")
    await userver.handle_client(reader, writer, handlers)
    await userver.finalise_client(reader, writer)
    print("exit...")


async def main():
    loop.create_task(asyncio.start_server(my_handle_client, "0.0.0.0", 7777))
    await asyncio.sleep(120)  # serve for 120 seconds
    # loop.run_forever()


loop = asyncio.get_event_loop()
loop.run_until_complete(main())
