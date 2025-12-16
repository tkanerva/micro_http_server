
# micro_http_server

## a simple http server for micropython and CPython which also happens to be fast


### examples

```
def my_post_handler(url, data) -> tuple:
    code, hdrs = 404, {}
    if url == "/users":
        for k, v in data.items():
            DB[k] = v
        code = 200
    return code, "", hdrs

def my_get_handler(url, data) -> tuple:
    return 200, "hello world!", {}

async def my_handle_client(reader, writer):
    handlers = {
        "get": my_get_handler,
        "post": my_post_handler,
    }
    await userver.handle_client(reader, writer, handlers)
    await userver.finalise_client(reader, writer)
    
async def main():
    loop.create_task(asyncio.start_server(my_handle_client, "0.0.0.0", 3000))

```



### speed

Not a design consideration, but.
Benchmarking a simple GET request handler, one request takes ~200 usec user time.
Running on a Macbook M1, a single core can serve approx 6000 requests/sec.

