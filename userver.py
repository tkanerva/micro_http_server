import os
import time
import json
import asyncio
import re


# from cpython's httplib
# Table mapping response codes to messages; entries have the
# form {code: (shortmessage, longmessage)}.
# See RFC 2616.
HTTP_RESPONSES = {
        100: ('Continue', 'Request received, please continue'),
        101: ('Switching Protocols',
              'Switching to new protocol; obey Upgrade header'),

        200: ('OK', 'Request fulfilled, document follows'),
        201: ('Created', 'Document created, URL follows'),
        202: ('Accepted',
              'Request accepted, processing continues off-line'),
        203: ('Non-Authoritative Information', 'Request fulfilled from cache'),
        204: ('No Content', 'Request fulfilled, nothing follows'),
        205: ('Reset Content', 'Clear input form for further input.'),
        206: ('Partial Content', 'Partial content follows.'),

        300: ('Multiple Choices',
              'Object has several resources -- see URI list'),
        301: ('Moved Permanently', 'Object moved permanently -- see URI list'),
        302: ('Found', 'Object moved temporarily -- see URI list'),
        303: ('See Other', 'Object moved -- see Method and URL list'),
        304: ('Not Modified',
              'Document has not changed since given time'),
        305: ('Use Proxy',
              'You must use proxy specified in Location to access this '
              'resource.'),
        307: ('Temporary Redirect',
              'Object moved temporarily -- see URI list'),

        400: ('Bad Request',
              'Bad request syntax or unsupported method'),
        401: ('Unauthorized',
              'No permission -- see authorization schemes'),
        402: ('Payment Required',
              'No payment -- see charging schemes'),
        403: ('Forbidden',
              'Request forbidden -- authorization will not help'),
        404: ('Not Found', 'Nothing matches the given URI'),
        405: ('Method Not Allowed',
              'Specified method is invalid for this resource.'),
        406: ('Not Acceptable', 'URI not available in preferred format.'),
        407: ('Proxy Authentication Required', 'You must authenticate with '
              'this proxy before proceeding.'),
        408: ('Request Timeout', 'Request timed out; try again later.'),
        409: ('Conflict', 'Request conflict.'),
        410: ('Gone',
              'URI no longer exists and has been permanently removed.'),
        411: ('Length Required', 'Client must specify Content-Length.'),
        412: ('Precondition Failed', 'Precondition in headers is false.'),
        413: ('Request Entity Too Large', 'Entity is too large.'),
        414: ('Request-URI Too Long', 'URI is too long.'),
        415: ('Unsupported Media Type', 'Entity body in unsupported format.'),
        416: ('Requested Range Not Satisfiable',
              'Cannot satisfy request range.'),
        417: ('Expectation Failed',
              'Expect condition could not be satisfied.'),

        500: ('Internal Server Error', 'Server got itself in trouble'),
        501: ('Not Implemented',
              'Server does not support this operation'),
        502: ('Bad Gateway', 'Invalid responses from another server/proxy.'),
        503: ('Service Unavailable',
              'The server cannot process the request due to a high load'),
        504: ('Gateway Timeout',
              'The gateway server did not receive a timely response'),
        505: ('HTTP Version Not Supported', 'Cannot fulfill request.'),
        }

HTTP_RESP = [
    "HTTP/1.1 {code} {shortmsg}",
    "Date: {datestr}",
    "Content-Length: {content_length}",
    "Content-Type: {content_type}; charset=utf-8",
    "",
    ]


def debugprint_(*args, **kw):
    print(*args, **kw)

def noprint_(*args, **kw):
    pass

if os.getenv("USERVER_DEBUG"):
    debugprint = debugprint_
else:
    debugprint = noprint_


STATE = {}


def rfc1123(timetuple):
    # return something like Sun, 21 Oct 2018 12:16:24 GMT

    y, m, d, H, M, S, wkday, yday, isdst = timetuple
    shortday = ['Mon','Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][wkday]
    shortmonth = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][m-1]
    s = f"{shortday}, {d:02} {shortmonth} {y:04} {H:02}:{M:02}:{S:02} GMT"
    return s


async def produce_response(reader, writer, handlerfun, request="", headers=[]):
    method_url, _, proto = request.rpartition(" ")
    method, _, url = method_url.partition(" ")
    debugprint(f"[{int(time.time())}] GET: URI = {url}, proto= {proto}")
    hdrs = parse_headers(headers)
    debugprint("HDRS: ", hdrs)

    # if we need to get data from client (POST), get payload
    if method == "PUT" or method == "POST" or method == "PATCH":
        clen = int(hdrs.get('content-length', 0))
        if not clen:
            debugprint("ERROR: no content-length found")
            data = None
        else:
            debugprint("got contentlength:", clen)
            data = await _get_payload(reader, clen)
    else:
        data = None

    # write a HTML response
    try:
        code, txt, hdrs = handlerfun(url, data)
    except Exception as e:
        debugprint("exception:", e)
        code, txt, hdrs = 500, "", {}

    writer.write(create_resp_headers(txt, code, hdrs).encode())
    writer.write(txt.encode())


async def _get_payload(reader, clen):
    buf = b""
    while len(buf) < clen:
        ch = await reader.read(1024)
        buf += ch
        if ch == b"":
            continue

    payload = buf.decode("utf8")
    return payload


def create_resp_headers(txt: str, code: int, d: dict) -> str:
    if not "content_type" in d:
        d.update({"content_type": "text/html"})
    d.update({"content_length": len(txt)})
    d.update({"timestamp": int(time.time())})
    d.update({"datestr": rfc1123(time.gmtime())})
    d.update({"code": code})
    d.update({"shortmsg": HTTP_RESPONSES.get(code, [""])[0]})
    lst = []
    for h in HTTP_RESP:
        tmp = h.format(**d)
        lst.append(tmp)
    return '\r\n'.join(lst) + '\r\n'


def parse_headers(lst):
    d = {"content-type": "text/html"}  # default
    r1 = re.compile(r"([a-zA-Z0-9-_]+):.?(.*?)$")
    for s in lst:
        m = r1.match(s)
        hdr, val = m.group(1), m.group(2)
        d[hdr.lower()] = val.lower().strip()
    return d


async def handle_client(reader, writer, handlers):
    emptyfun = lambda x, y: (405, "method not allowed", {})
    debugprint('New client connected.')
    lines = []
    in_headers = True
    while in_headers:
        line = (await reader.readline()).decode('utf8')
        lines.append(line)
        if line.strip() == '':
            in_headers = False
        debugprint(f'Received: {line.strip()}')

    hdrs = [x for x in lines if ":" in x]

    # get the method from this request
    request = lines[0].strip()
    verb, _, url_proto = request.partition(" ")
    handlerfun = handlers.get(verb.lower(), emptyfun)
    debugprint("using handlerfun: ", handlerfun)
    await produce_response(reader, writer, handlerfun=handlerfun, request=request, headers=hdrs)


async def finalise_client(reader, writer):
    writer.close()
    await writer.wait_closed()
    debugprint('client disconnected.')
