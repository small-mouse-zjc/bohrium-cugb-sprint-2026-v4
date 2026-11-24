#!/usr/bin/env python3
"""09 真 TriG 解析（标准库实现，不依赖 rdflib）。

只覆盖本 Skill 自己产出的 TriG 子集：@prefix、命名图块、IRI/PNAME 主谓宾、
字符串字面量（含转义与 ^^datatype / @lang）。但它做的是**语法解析**，不是
正则计数：括号必须闭合、每条三元组必须以 `.` 结束、字面量必须闭合且转义合法、
主语不得是字面量。坏输出会抛 TrigSyntaxError 而不是被数出来。

这样 `export_roundtrip` 才真的在证明"导出的 TriG 结构可读"。
"""
import re

PNAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]*:[A-Za-z0-9_.%-]*")
LANG_RE = re.compile(r"@[A-Za-z]+(?:-[A-Za-z0-9]+)*")
ESCAPES = {'"': '"', "\\": "\\", "n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f"}


class TrigError(Exception):
    def __init__(self, msg, pos):
        super().__init__(f"{msg} (pos {pos})")
        self.msg, self.pos = msg, pos


def tokenize(text):
    toks, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
            continue
        if c == "#":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if c == "<":
            j = text.find(">", i + 1)
            if j < 0:
                raise TrigError("IRI 未闭合（缺 >）", i)
            iri = text[i + 1:j]
            if not iri.strip() or re.search(r"[\s<\"{}]", iri):
                raise TrigError("IRI 含空白/非法字符", i)
            toks.append(("IRI", iri, i))
            i = j + 1
            continue
        if c == '"':
            j, buf, start = i + 1, [], i
            while True:
                if j >= n:
                    raise TrigError("字符串字面量未闭合", start)
                ch = text[j]
                if ch == "\\":
                    if j + 1 >= n:
                        raise TrigError("转义符后没有字符", j)
                    e = text[j + 1]
                    if e not in ESCAPES:
                        raise TrigError(f"非法转义 \\{e}", j)
                    buf.append(ESCAPES[e])
                    j += 2
                    continue
                if ch == '"':
                    break
                if ch == "\n":
                    raise TrigError("字面量里有裸换行（缺转义）", j)
                buf.append(ch)
                j += 1
            toks.append(("STRING", "".join(buf), start))
            i = j + 1
            continue
        if c in "{}.;,()":
            toks.append(("PUNCT", c, i))
            i += 1
            continue
        if c == "@":
            if text.startswith("@prefix", i):
                toks.append(("KEYWORD", "@prefix", i))
                i += 7
                continue
            if text.startswith("@base", i):
                toks.append(("KEYWORD", "@base", i))
                i += 5
                continue
            m = LANG_RE.match(text, i)
            if m:
                toks.append(("LANG", m.group(0), i))
                i = m.end()
                continue
            raise TrigError("无法识别的 @ 记号", i)
        if text.startswith("^^", i):
            toks.append(("PUNCT", "^^", i))
            i += 2
            continue
        m = PNAME_RE.match(text, i)
        if m:
            toks.append(("PNAME", m.group(0), i))
            i = m.end()
            continue
        if text[i:i + 1] == "a" and (i + 1 >= n or text[i + 1] in " \t\r\n<"):
            toks.append(("KEYWORD", "a", i))
            i += 1
            continue
        raise TrigError(f"无法识别的记号 {c!r}", i)
    toks.append(("EOF", "", n))
    return toks


class Parser:
    def __init__(self, toks):
        self.t, self.i = toks, 0
        self.prefixes = {}
        self.graphs = []
        self.triples = []

    def peek(self, k=0):
        return self.t[self.i + k]

    def next(self):
        tok = self.t[self.i]
        self.i += 1
        return tok

    def expect(self, typ, val=None, msg=""):
        tok = self.next()
        if tok[0] != typ or (val is not None and tok[1] != val):
            raise TrigError(msg or f"期望 {typ} {val or ''}，实际 {tok[0]} {tok[1]!r}", tok[2])
        return tok

    def expand(self, tok):
        if tok[0] == "IRI":
            return tok[1]
        if tok[0] == "KEYWORD" and tok[1] == "a":
            return "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
        if tok[0] == "PNAME":
            name, local = tok[1].split(":", 1)
            if name not in self.prefixes:
                raise TrigError(f"未声明的前缀 {name}:", tok[2])
            return self.prefixes[name] + local
        raise TrigError(f"这里要 IRI，实际是 {tok[0]}", tok[2])

    def parse(self):
        while True:
            tok = self.peek()
            if tok[0] == "EOF":
                break
            if tok[0] == "KEYWORD" and tok[1] == "@prefix":
                self.next()
                pre = self.expect("PNAME", msg="@prefix 后要 prefix: ")
                self.expect("IRI", msg="@prefix 后要 <IRI>")
                iri = self.t[self.i - 1][1]
                self.expect("PUNCT", ".", msg="@prefix 声明必须以 . 结束")
                self.prefixes[pre[1].rstrip(":")] = iri
                continue
            if tok[0] == "KEYWORD" and tok[1] == "@base":
                raise TrigError("本 Skill 不产出 @base，遇到即视为非预期语法", tok[2])
            graph = None
            if tok[0] in ("IRI", "PNAME") and self.peek(1)[0] == "PUNCT" and self.peek(1)[1] == "{":
                graph = self.expand(self.next())
                self.next()
                self.graphs.append(graph)
                self.triples_block(graph, until="}")
                self.expect("PUNCT", "}", msg="命名图块缺 }")
                if self.peek()[0] == "PUNCT" and self.peek()[1] in ".{}":
                    if self.peek()[1] == ".":
                        self.next()
                continue
            if tok[0] == "PUNCT" and tok[1] == "{":
                raise TrigError("默认图块（无标签 { }）本 Skill 不产出", tok[2])
            self.triples_block(graph, until=".")
        return self.triples

    def triples_block(self, graph, until):
        """解析一组三元组，直到遇到 until 结束符。"""
        while True:
            tok = self.peek()
            if tok[0] == "EOF":
                raise TrigError("三元组块意外结束（缺 . 或 }）", tok[2])
            if tok[0] == "PUNCT" and tok[1] == until:
                return
            s = self.expand(self.next())
            self.predicate_object_list(graph, s)
            self.expect("PUNCT", ".", msg=f"三元组必须以 . 结束（主语 {s}）")

    def predicate_object_list(self, graph, s):
        while True:
            p = self.expand(self.next())
            while True:
                o, kind = self.object_()
                self.triples.append({"g": graph, "s": s, "p": p, "o": o, "kind": kind})
                if self.peek()[0] == "PUNCT" and self.peek()[1] == ",":
                    self.next()
                    continue
                break
            if self.peek()[0] == "PUNCT" and self.peek()[1] == ";":
                self.next()
                nxt = self.peek()
                if nxt[0] == "PUNCT" and nxt[1] in ".;}":
                    return
                continue
            return

    def object_(self):
        tok = self.next()
        if tok[0] == "IRI" or tok[0] == "PNAME" or (tok[0] == "KEYWORD" and tok[1] == "a"):
            return self.expand(tok), "iri"
        if tok[0] == "STRING":
            o = tok[1]
            nxt = self.peek()
            if nxt[0] == "PUNCT" and nxt[1] == "^^":
                self.next()
                dt = self.expect("IRI", msg="^^ 后要 datatype IRI")
                o = {"value": o, "datatype": dt[1]}
            elif nxt[0] == "LANG":
                self.next()
                o = {"value": o, "lang": nxt[1]}
            return o, "literal"
        raise TrigError(f"宾语位置非法（{tok[0]} {tok[1]!r}）；主语/宾语不得裸写", tok[2])


def parse(text):
    """解析 TriG 文本，返回 {prefixes, graphs, triples}；语法错误抛 TrigError。"""
    p = Parser(tokenize(text or ""))
    triples = p.parse()
    return {"prefixes": p.prefixes, "graphs": p.graphs, "triples": triples}


def summarize(parsed, nschema="http://www.nanopub.org/nschema#",
              rel="https://example.org/rel/"):
    """数命名图、np:Assertion 节点、rel:quote 字面量。"""
    rdf_type = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
    assert_graph_ids = {t["g"] for t in parsed["triples"]
                        if t["p"] == rdf_type and t["o"] == nschema + "Assertion" and t["kind"] == "iri"}
    assertion_nodes = {t["s"] for t in parsed["triples"]
                       if t["p"] == rdf_type and t["o"] == nschema + "Assertion"}
    quotes = [t for t in parsed["triples"] if t["p"] == rel + "quote" and t["kind"] == "literal"]
    return {"named_graphs": len(assert_graph_ids), "assertion_nodes": len(assertion_nodes),
            "quotes": len(quotes), "triples": len(parsed["triples"])}
