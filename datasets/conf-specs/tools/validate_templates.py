#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_templates.py —— 用 schema/template.schema.json 校验 templates-v2/*.json。

本机无 jsonschema 包，这里实现所需子集：type/required/enum/const/pattern/
minimum/minItems/maxItems/items/properties/additionalProperties/$ref。
用法: python3 tools/validate_templates.py [文件...]
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA = json.load(open(os.path.join(ROOT, "schema", "template.schema.json"), encoding="utf-8"))

TYPES = {"object": dict, "array": list, "string": str, "integer": int,
         "number": (int, float), "boolean": bool, "null": type(None)}


def resolve(ref, schema):
    assert ref.startswith("#/"), ref
    node = schema
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def check(inst, sch, path, errs, schema):
    if "$ref" in sch:
        sch = dict(resolve(sch["$ref"], schema))
    if "const" in sch and inst != sch["const"]:
        errs.append(f"{path}: 期望常量 {sch['const']!r}，实际 {inst!r}")
    if "enum" in sch and inst not in sch["enum"]:
        errs.append(f"{path}: 值 {inst!r} 不在枚举 {sch['enum']}")
    t = sch.get("type")
    if t is not None:
        types = [t] if isinstance(t, str) else list(t)
        ok = False
        for tt in types:
            py = TYPES.get(tt)
            if py is None:
                ok = True
                continue
            if tt in ("integer", "number") and isinstance(inst, bool):
                continue
            if isinstance(inst, py):
                ok = True
        if not ok:
            errs.append(f"{path}: 类型应为 {t}，实际 {type(inst).__name__}")
            return
    if isinstance(inst, str) and "pattern" in sch and not re.search(sch["pattern"], inst):
        errs.append(f"{path}: 字符串 {inst!r} 不匹配 {sch['pattern']}")
    if isinstance(inst, (int, float)) and not isinstance(inst, bool):
        if "minimum" in sch and inst < sch["minimum"]:
            errs.append(f"{path}: {inst} < minimum {sch['minimum']}")
    if isinstance(inst, list):
        if "minItems" in sch and len(inst) < sch["minItems"]:
            errs.append(f"{path}: 数组长度 {len(inst)} < minItems {sch['minItems']}")
        if "maxItems" in sch and len(inst) > sch["maxItems"]:
            errs.append(f"{path}: 数组长度 {len(inst)} > maxItems {sch['maxItems']}")
        if "items" in sch:
            for i, v in enumerate(inst):
                check(v, sch["items"], f"{path}[{i}]", errs, schema)
    if isinstance(inst, dict):
        for req in sch.get("required", []):
            if req not in inst:
                errs.append(f"{path}: 缺少必填字段 {req!r}")
        props = sch.get("properties", {})
        for k, v in inst.items():
            if k in props:
                check(v, props[k], f"{path}.{k}", errs, schema)
            else:
                ap = sch.get("additionalProperties")
                if ap is False:
                    errs.append(f"{path}: 出现未定义字段 {k!r}")
                elif isinstance(ap, dict):
                    check(v, ap, f"{path}.{k}", errs, schema)


def main():
    files = sys.argv[1:]
    if not files:
        d = os.path.join(ROOT, "templates-v2")
        files = [os.path.join(d, f) for f in sorted(os.listdir(d)) if f.endswith(".json")]
    bad = 0
    for p in files:
        inst = json.load(open(p, encoding="utf-8"))
        errs = []
        check(inst, SCHEMA, os.path.basename(p), errs, SCHEMA)
        if errs:
            bad += 1
            print(f"[FAIL] {os.path.basename(p)}")
            for e in errs[:20]:
                print("   ", e)
        else:
            print(f"[OK]   {os.path.basename(p)}")
    print(f"\n文件数 {len(files)}  失败 {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
