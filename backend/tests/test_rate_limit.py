"""Requests per visitor: a flood or a run of guessed codes gets 429, other
visitors and the MCP server's own calls do not notice."""

import asyncio

from app.rate_limit import INTERNAL_TOKEN, RateLimit


def _app(status=200):
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": status, "headers": []})
        await send({"type": "http.response.body", "body": b""})
    return app


def _call(limiter, path, ip="1.2.3.4", headers=()):
    sent = []

    async def send(message):
        sent.append(message)

    scope = {"type": "http", "path": path, "headers": list(headers), "client": (ip, 1)}
    asyncio.run(limiter(scope, None, send))
    return sent[0]["status"]


def test_a_visitor_over_the_limit_waits_others_do_not():
    limiter = RateLimit(_app(), rules=[("/api/", 3, 60)], enabled=True)
    assert [_call(limiter, "/api/x") for _ in range(4)] == [200, 200, 200, 429]
    assert _call(limiter, "/api/x", ip="5.6.7.8") == 200
    internal = [(b"x-heattransplan-internal", INTERNAL_TOKEN.encode())]
    assert _call(limiter, "/api/x", headers=internal) == 200


def test_guessed_codes_lock_the_live_endpoints():
    limiter = RateLimit(_app(404), rules=[], misses=(2, 600), enabled=True)
    assert [_call(limiter, "/api/live/pages/abcd1234") for _ in range(3)] == [404, 404, 429]
    assert _call(limiter, "/api/live/pages/abcd1234", ip="5.6.7.8") == 404


def test_codes_the_mcp_server_tries_count_for_its_caller():
    """The MCP server's lookups carry INTERNAL_TOKEN and the agent's address:
    unknown codes count against that address, and its lock-out stops them
    too. The address header counts for nothing without the token."""
    from app.rate_limit import CALLER_HEADER

    limiter = RateLimit(_app(404), rules=[("/api/", 1, 60)], misses=(2, 600), enabled=True)
    internal = (b"x-heattransplan-internal", INTERNAL_TOKEN.encode())
    agent = [internal, (CALLER_HEADER, b"9.9.9.9")]
    # Internal calls do not use up the request limit (the /mcp request did) ...
    assert [_call(limiter, "/api/live/pages/abcd1234", ip="127.0.0.1", headers=agent)
            for _ in range(3)] == [404, 404, 429]
    # ... and the agent's own address is locked out as well.
    assert _call(limiter, "/api/live/pages/abcd1234", ip="9.9.9.9") == 429
    # A forged address without the token is ignored: the real one counts.
    assert _call(limiter, "/api/live/pages/abcd1234", ip="5.6.7.8",
                 headers=[(CALLER_HEADER, b"1.1.1.1")]) == 404
    assert _call(limiter, "/api/live/pages/abcd1234", ip="1.1.1.1") == 404
    # Without a caller (a local MCP server's own calls) nothing counts, as before.
    assert _call(limiter, "/api/live/pages/abcd1234", ip="127.0.0.1", headers=[internal]) == 404


def test_an_ipv6_visitor_is_counted_by_their_64():
    """Any address in one /64 is the same visitor; IPv4 stays as it is."""
    from app.rate_limit import visitor
    assert visitor("2001:db8:1:2::1") == visitor("2001:db8:1:2:ffff::9") == "2001:db8:1:2::/64"
    assert visitor("2001:db8:1:3::1") != visitor("2001:db8:1:2::1")
    assert visitor("203.0.113.7") == "203.0.113.7"
    assert visitor("::ffff:203.0.113.7") == "203.0.113.7"
    assert visitor("unknown") == "unknown"
