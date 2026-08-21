import os
import glob

from src.ingestion.msg_reader import read_msg

SRC = "/home/bento/transferencia/email"
F = sorted(glob.glob(os.path.join(SRC, "**", "*.msg"), recursive=True))[0]


def test_read_msg_returns_metadata():
    d = read_msg(F)
    assert d["subject"]  # nunca vazio
    assert d["sender_email"] or d["sender"]
    assert d["date"]  # string não vazia


def test_read_msg_attachments_are_bytes():
    d = read_msg(F)
    for att in d["attachments"]:
        assert isinstance(att["data"], bytes)
        assert att["name"]
