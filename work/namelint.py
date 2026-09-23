# -*- coding: utf-8 -*-
"""简易静态检查：找出函数里用到但没导入/没定义的名字（防止漏 import）。"""
from __future__ import annotations

import ast
import builtins
import pathlib
import sys

BUILTINS = set(dir(builtins)) | {"__file__", "__name__", "__doc__", "__package__", "self", "cls"}


def collect_names(node, names: set, descend_into_functions: bool = True) -> None:
    """收集某个作用域里"产生名字"的语句（不进入嵌套函数体，避免把局部变量当成全局）。"""
    body = getattr(node, "body", [])
    for sub in body:
        if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(sub.name)
            if descend_into_functions:
                for arg in list(getattr(sub, "args", ast.arguments()).args) if hasattr(sub, "args") else []:
                    names.add(arg.arg)
            continue
        if isinstance(sub, (ast.Import, ast.ImportFrom)):
            for alias in sub.names:
                names.add((alias.asname or alias.name).split(".")[0])
            continue
        if isinstance(sub, ast.Global) or isinstance(sub, ast.Nonlocal):
            names.update(sub.names)
            continue
        if isinstance(sub, ast.Try):
            for part in sub.body + sub.orelse + sub.finalbody:
                collect_names(ast.Module(body=[part], type_ignores=[]), names, descend_into_functions)
            for handler in sub.handlers:
                if handler.name:
                    names.add(handler.name)
                collect_names(ast.Module(body=handler.body, type_ignores=[]), names, descend_into_functions)
            continue
        for inner in ast.walk(sub):
            if isinstance(inner, ast.Name) and isinstance(inner.ctx, (ast.Store, ast.Del)):
                names.add(inner.id)
            elif isinstance(inner, ast.arg):
                names.add(inner.arg)
            elif isinstance(inner, ast.ExceptHandler) and inner.name:
                names.add(inner.name)


def check_file(path: pathlib.Path) -> list:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    module_names: set = set()
    collect_names(tree, module_names, descend_into_functions=False)
    problems = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        local = set(module_names)
        collect_names(node, local)
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
                if sub.id not in local and sub.id not in BUILTINS:
                    problems.append((path.name, node.name, sub.lineno, sub.id))
    # 模块级代码也检查一遍
    for sub in ast.walk(tree):
        if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load) and isinstance(getattr(sub, "ctx", None), ast.Load):
            if sub.id not in module_names and sub.id not in BUILTINS:
                problems.append((path.name, "<module>", sub.lineno, sub.id))
    return problems


def main() -> int:
    root = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path("app")
    total = 0
    for path in sorted(root.glob("*.py")):
        for name, func, line, ident in check_file(path):
            print("%s:%s 在 %s() 里使用了未定义的名字：%s" % (name, line, func, ident))
            total += 1
    print("共发现 %d 处可疑的未定义名字" % total)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
