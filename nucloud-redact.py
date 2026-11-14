"""The secret filter of the nucloud template, stdin to stdout: makehelp-nucloud.sh passes the suite's output and its
copied service logs through it, and the runner (scripts/testing-full-run.py) the logs it keeps. It masks this run's
secret values, Izuma API keys and private keys, including private keys a suite prints base64-encoded.

  * a PEM private key, on one line or several, becomes <redacted ... private key>.
  * a base64 token of 100+ characters (standard or URL-safe alphabet) is masked when it decodes to text holding
    "PRIVATE KEY-----" (a PEM key, alone or beside a certificate, or inside JSON), or to DER that opens like a
    private key: SEQUENCE, then INTEGER version 0, 1 or 3 (PKCS#8, PKCS#1, SEC1, PKCS#12).
  * a run of whole-line base64 (a wrapped blob, 40+ characters a line) is decoded as one and masked the same way;
    the run is held until its next other line (at most 400 lines), then written.
Certificates, public keys and ordinary payloads decode to neither, so they pass unchanged.
"""
import base64, binascii, os, re, sys

key = re.compile(r"\bak_[0-9A-Za-z]{20,}")
whole = re.compile(r"-----BEGIN ([A-Z ]*)PRIVATE KEY-----.*?-----END \1PRIVATE KEY-----")
opened = re.compile(r"-----BEGIN ([A-Z ]*)PRIVATE KEY-----.*")
token = re.compile(r"(?<![A-Za-z0-9+/_-])[A-Za-z0-9+/_-]{100,}={0,2}")
b64line = re.compile(r"[A-Za-z0-9+/_-]{40,}={0,2}")
MASK = "<redacted base64 private key>"
HELD = 400  # wrapped-blob lines held back at most; a 4096-bit RSA key wraps to about 50


def decoded(text):
    s = text.rstrip("=")
    s += "=" * (-len(s) % 4)
    for alt in (None, b"-_"):
        try:
            return base64.b64decode(s, altchars=alt, validate=True)
        except (binascii.Error, ValueError):
            pass
    return b""


def private(raw):
    if b"PRIVATE KEY-----" in raw:
        return True
    if len(raw) < 64 or raw[0] != 0x30:
        return False
    n = raw[1]
    i = 2 + (n & 0x7F if n & 0x80 else 0)  # past the outer SEQUENCE length
    return raw[i:i + 2] == b"\x02\x01" and raw[i + 2:i + 3] in (b"\x00", b"\x01", b"\x03")


def masked(line):
    return token.sub(lambda m: MASK if private(decoded(m.group(0))) else m.group(0), line)


def run(lines, environ=os.environ):
    """Yield the filtered lines, each as soon as it is final; environ names this run's secret values."""
    keys = ["NUCLOUD_API_KEY", "NUCLOUD_PASSWORD", "NUCLOUD_ROOT_PASSWORD"] + [k for k in environ if re.fullmatch(r"NUCLOUD_ACCOUNT_\w+_(API_KEY|PASSWORD)", k)]
    vals = sorted({environ.get(k, "") for k in keys} - {""}, key=len, reverse=True)
    vals = [v for v in vals if len(v) >= 6]
    pem, held = False, []

    def flush():  # a held run of whole-line base64: one mask line when it decodes to a key, else the lines in order
        blob = "".join(l.strip() for l in held)
        out = [MASK + "\n"] if len(held) > 1 and private(decoded(blob)) else [masked(l) for l in held]
        del held[:]
        return out

    for line in lines:
        for v in vals:
            line = line.replace(v, "<redacted>")
        line = key.sub("ak_<redacted>", line)
        if pem:  # inside a multi-line key: drop lines up to and including its END line
            if re.search(r"-----END [A-Z ]*PRIVATE KEY-----", line):
                pem = False
            continue
        line = whole.sub(r"<redacted \1private key>", line)  # a key on one line (JSON with escaped newlines)
        if opened.search(line):
            yield from flush()
            pem = True
            line = opened.sub(r"<redacted \1private key>", line).rstrip("\n") + "\n"
        if b64line.fullmatch(line.strip()):
            held.append(line)
            if len(held) >= HELD:
                yield from flush()
            continue
        yield from flush()
        yield masked(line)
    yield from flush()


if __name__ == "__main__":  # a stream: each line is written and flushed as soon as it is final
    for out in run(sys.stdin):
        sys.stdout.write(out)
        sys.stdout.flush()
