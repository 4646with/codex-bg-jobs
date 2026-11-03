"""Deliver a tool result through the local Codex desktop thread owner.

Exit 2 only before dispatch, when the caller can safely try codex queue.
"""
import json
import os
import socket
import struct
import sys
import time
import uuid


def request(sock, stream, client, method, params, version, target=None):
    identifier = str(uuid.uuid4())
    message = dict(type="request", requestId=identifier, sourceClientId=client,
                   method=method, params=params, version=version)
    if target:
        message["targetClientId"] = target
    body = json.dumps(message).encode()
    sock.sendall(struct.pack("=I", len(body)) + body)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        size, = struct.unpack("=I", stream.read(4))
        if size > 16 * 1024 * 1024:
            raise ValueError("oversized IPC frame")
        reply = json.loads(stream.read(size))
        if reply.get("requestId") == identifier and reply.get("type") == "response":
            if reply.get("resultType") != "success":
                raise ValueError(f"{method} rejected")
            return reply
    raise TimeoutError(method)


def main():
    thread = sys.argv[1]
    output = sys.stdin.read()
    home = os.environ.get("CODEX_HOME") or os.path.expanduser("~/.codex")
    dispatched = False
    try:
        with socket.socket(socket.AF_UNIX) as sock, sock.makefile("rb") as stream:
            sock.settimeout(10)
            sock.connect(os.path.join(home, "ipc", "ipc.sock"))
            init = request(sock, stream, "uninitialized", "initialize",
                           {"clientType": "bg-jobs"}, 0)
            client = init["result"]["clientId"]
            owner = request(sock, stream, client, "thread-owner-discovery",
                            {"hostId": "local", "conversationId": thread}, 1)
            target = owner["handledByClientId"]
            if not target:
                raise ValueError("missing thread owner")
            turn = dict(threadId=thread, input=[], toolOutput=dict(
                name="bg_job_completed", namespace=None, output=output))
            dispatched = True
            reply = request(sock, stream, client, "thread-follower-start-turn",
                            dict(conversationId=thread, turnStart=dict(request=turn)), 2, target)
            print("native turn", reply["result"]["result"]["turn"]["id"])
            return 0
    except (OSError, ValueError, KeyError, TypeError, struct.error) as error:
        print("native delivery:", error, file=sys.stderr)
        return 1 if dispatched else 2


if __name__ == "__main__":
    sys.exit(main())
