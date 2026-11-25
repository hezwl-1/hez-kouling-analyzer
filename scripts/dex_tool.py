#!/usr/bin/env python3
"""
通用 DEX 解析器 — APK 逆向的底层工具

不依赖 jadx/apktool，直接用 Python 解析 DEX 结构。适用于：
- 按字符串反查引用它的类和方法（最常用的入口定位手段）
- 反汇编指定方法的字节码，看清调用了哪些 API
- 导出全量字符串、API 路径

实战验证：网易云音乐 9.x（21 个 dex / 190MB 字节码）

CLI:
    python dex_tool.py strings  <apk_dir>                    # 导出全部字符串
    python dex_tool.py apis     <apk_dir>                    # 提取 API 路径
    python dex_tool.py find     <apk_dir> <keyword>          # 字符串反查引用类
    python dex_tool.py disasm   <dex_file> <Class;> <method> # 反汇编方法
    python dex_tool.py methods  <dex_file> <Class;>          # 列出类的方法
"""

import struct
import sys
import os
import glob
import re


# ---------------------------------------------------------------- DEX 基础解析

def uleb128(b, p):
    """读取 uleb128 变长整数，返回 (值, 新位置)"""
    r = 0
    s = 0
    while True:
        x = b[p]
        p += 1
        r |= (x & 0x7F) << s
        if not (x & 0x80):
            break
        s += 7
    return r, p


class Dex:
    """单个 DEX 文件的解析器"""

    def __init__(self, path):
        self.path = path
        self.d = open(path, 'rb').read()
        d = self.d

        # DEX header 固定偏移（注意：必须逐项用固定偏移读，不能连续 unpack，易错位）
        self.string_ids_size = struct.unpack_from('<I', d, 0x38)[0]
        self.string_ids_off = struct.unpack_from('<I', d, 0x3C)[0]
        self.type_ids_size = struct.unpack_from('<I', d, 0x40)[0]
        self.type_ids_off = struct.unpack_from('<I', d, 0x44)[0]
        self.proto_ids_size = struct.unpack_from('<I', d, 0x48)[0]
        self.proto_ids_off = struct.unpack_from('<I', d, 0x4C)[0]
        self.field_ids_size = struct.unpack_from('<I', d, 0x50)[0]
        self.field_ids_off = struct.unpack_from('<I', d, 0x54)[0]
        self.method_ids_size = struct.unpack_from('<I', d, 0x58)[0]
        self.method_ids_off = struct.unpack_from('<I', d, 0x5C)[0]
        self.class_defs_size = struct.unpack_from('<I', d, 0x60)[0]
        self.class_defs_off = struct.unpack_from('<I', d, 0x64)[0]

        self._strs = {}
        self._types = {}
        self._protos = {}
        self._fields = {}
        self._methods = {}

    def string(self, idx):
        if idx in self._strs:
            return self._strs[idx]
        d = self.d
        off = struct.unpack_from('<I', d, self.string_ids_off + idx * 4)[0]
        _, p = uleb128(d, off)  # 跳过 utf16 长度
        start = p
        while d[p] != 0:
            p += 1
        s = d[start:p].decode('utf-8', 'replace')
        self._strs[idx] = s
        return s

    def type_str(self, idx):
        if idx in self._types:
            return self._types[idx]
        si = struct.unpack_from('<I', self.d, self.type_ids_off + idx * 4)[0]
        s = self.string(si)
        self._types[idx] = s
        return s

    def proto(self, idx):
        """返回 (返回类型, [参数类型])"""
        if idx in self._protos:
            return self._protos[idx]
        base = self.proto_ids_off + idx * 12
        ret = struct.unpack_from('<I', self.d, base + 4)[0]
        params_off = struct.unpack_from('<I', self.d, base + 8)[0]
        params = []
        if params_off:
            n = struct.unpack_from('<I', self.d, params_off)[0]
            for i in range(n):
                t = struct.unpack_from('<H', self.d, params_off + 4 + i * 2)[0]
                params.append(self.type_str(t))
        v = (self.type_str(ret), params)
        self._protos[idx] = v
        return v

    def field(self, idx):
        if idx in self._fields:
            return self._fields[idx]
        cls, typ, name = struct.unpack_from(
            '<HHI', self.d, self.field_ids_off + idx * 8)
        v = (self.type_str(cls), self.type_str(typ), self.string(name))
        self._fields[idx] = v
        return v

    def method(self, idx):
        """返回 (类, 方法名, [参数], 返回类型)"""
        if idx in self._methods:
            return self._methods[idx]
        cls, proto, name = struct.unpack_from(
            '<HHI', self.d, self.method_ids_off + idx * 8)
        r, ps = self.proto(proto)
        v = (self.type_str(cls), self.string(name), ps, r)
        self._methods[idx] = v
        return v

    # ------------------------------------------------------------ 类遍历

    def iter_classes(self):
        """遍历所有类，yield (类名, class_data_off)"""
        for ci in range(self.class_defs_size):
            off = self.class_defs_off + ci * 32
            class_idx = struct.unpack_from('<I', self.d, off)[0]
            class_data_off = struct.unpack_from('<I', self.d, off + 24)[0]
            yield self.type_str(class_idx), class_data_off

    def iter_methods(self, class_data_off):
        """
        遍历 class_data 中的所有方法，yield (method_idx, code_off)

        关键：class_data 里字段和方法的计数必须拆成 static / instance 两组
        分别读取，合并成一个循环会导致索引漂移（实战踩过的坑）。
        """
        d = self.d
        p = class_data_off
        sf, p = uleb128(d, p)   # static fields
        inf, p = uleb128(d, p)  # instance fields
        dm, p = uleb128(d, p)   # direct methods
        vm, p = uleb128(d, p)   # virtual methods

        # 跳过 static fields
        for _ in range(sf):
            _, p = uleb128(d, p)  # field_idx_diff
            _, p = uleb128(d, p)  # access_flags
        # 跳过 instance fields（必须单独循环）
        for _ in range(inf):
            _, p = uleb128(d, p)
            _, p = uleb128(d, p)

        for cnt in (dm, vm):
            idx = 0
            for _ in range(cnt):
                diff, p = uleb128(d, p)
                idx += diff
                _, p = uleb128(d, p)          # access_flags
                code_off, p = uleb128(d, p)   # code_off
                yield idx, code_off

    def find_method(self, class_name, method_name):
        """定位方法，返回 (method_idx, code_off) 或 None"""
        for cname, cdo in self.iter_classes():
            if cname != class_name or not cdo:
                continue
            for idx, co in self.iter_methods(cdo):
                if idx >= self.method_ids_size:
                    continue
                if self.method(idx)[1] == method_name and co:
                    return idx, co
        return None


# ---------------------------------------------------------- 指令宽度表（Dalvik）

# 指令占用的 16-bit code unit 数，按 opcode 索引
WIDTH = [1] * 256
_WIDTH_OVERRIDES = {
    0x02: 2, 0x03: 3, 0x05: 2, 0x06: 3, 0x08: 2, 0x09: 3,
    0x13: 2, 0x14: 3, 0x15: 2, 0x16: 2, 0x17: 3, 0x18: 5, 0x19: 2,
    0x1A: 2, 0x1B: 3, 0x1C: 2, 0x1F: 2, 0x20: 2, 0x22: 2, 0x23: 2,
    0x24: 3, 0x25: 3, 0x26: 3, 0x29: 2, 0x2A: 3, 0x2B: 3, 0x2C: 3,
    0xFA: 5, 0xFB: 5, 0xFC: 3, 0xFD: 3, 0xFE: 3, 0xFF: 3,
}
# 0x2D..0x3D（cmp/if-test）、0x44..0x6D（aget/aput 系 + 二元运算）、
# 0x6E..0x72（invoke 系）、0x74..0x8F 等都是 2 或 3 unit，统一按范围处理
for _op in list(range(0x2D, 0x3E)) + list(range(0x44, 0x6E)):
    _WIDTH_OVERRIDES.setdefault(_op, 2)
for _op in list(range(0x6E, 0x73)) + list(range(0x74, 0x90)) + list(range(0x90, 0xE3)):
    _WIDTH_OVERRIDES.setdefault(_op, 3)
for _op, _w in _WIDTH_OVERRIDES.items():
    WIDTH[_op] = _w


def code_uses_strings(dex, code_off, str_idxs):
    """检查方法字节码里是否引用了指定字符串集合（只看 const-string 指令）"""
    d = dex.d
    insns_size = struct.unpack_from('<I', d, code_off + 12)[0]
    base = code_off + 16
    limit = base + insns_size * 2
    i = base
    while i < limit:
        if i + 2 > limit:
            break
        unit = struct.unpack_from('<H', d, i)[0]
        op = unit & 0xFF
        if op == 0x1A and i + 4 <= limit:          # const-string
            if struct.unpack_from('<H', d, i + 2)[0] in str_idxs:
                return True
        elif op == 0x1B and i + 6 <= limit:        # const-string/jumbo
            if struct.unpack_from('<I', d, i + 2)[0] in str_idxs:
                return True
        i += WIDTH[op] * 2
    return False


def disasm_method(dex, code_off, max_insns=400):
    """反汇编方法，返回可读指令列表"""
    d = dex.d
    insns_size = struct.unpack_from('<I', d, code_off + 12)[0]
    base = code_off + 16
    limit = base + insns_size * 2
    i = base
    out = []
    while i < limit and len(out) < max_insns:
        unit = struct.unpack_from('<H', d, i)[0]
        op = unit & 0xFF
        w = WIDTH[op]
        offset = i - base
        txt = ''

        if op == 0x1A and i + 4 <= limit:
            sidx = struct.unpack_from('<H', d, i + 2)[0]
            txt = f'const-string v{(unit >> 8) & 0xFF}, "{dex.string(sidx)}"'
        elif op == 0x1B and i + 6 <= limit:
            sidx = struct.unpack_from('<I', d, i + 2)[0]
            txt = f'const-string/jumbo v{(unit >> 8) & 0xFF}, "{dex.string(sidx)}"'
        elif 0x6E <= op <= 0x72 and i + 6 <= limit:
            midx = struct.unpack_from('<H', d, i + 2)[0]
            if midx < dex.method_ids_size:
                c, nm, ps, r = dex.method(midx)
                kind = {0x6E: 'invoke-virtual', 0x6F: 'invoke-super',
                        0x70: 'invoke-direct', 0x71: 'invoke-static',
                        0x72: 'invoke-interface'}[op]
                txt = f'{kind} {c}->{nm}({", ".join(ps)}){r}'
        elif op in (0x22, 0x23) and i + 4 <= limit:
            txt = 'new-instance ' + dex.type_str(
                struct.unpack_from('<H', d, i + 2)[0])
        elif op == 0x1F and i + 4 <= limit:
            txt = 'check-cast ' + dex.type_str(
                struct.unpack_from('<H', d, i + 2)[0])

        out.append(f'{offset:05x}: {txt}')
        i += w * 2
    return out


def scan_strings_in_code(dex, target_substr):
    """
    核心能力：找出所有引用了「包含某子串的字符串」的方法。
    返回 [(类名, 方法名)] —— 这是定位 API 调用点的最快路径。
    """
    # 先定位匹配的字符串索引
    str_idxs = set()
    for i in range(dex.string_ids_size):
        try:
            if target_substr in dex.string(i):
                str_idxs.add(i)
        except Exception:
            continue
    if not str_idxs:
        return []

    hits = []
    for cname, cdo in dex.iter_classes():
        if not cdo:
            continue
        for midx, co in dex.iter_methods(cdo):
            if not co or midx >= dex.method_ids_size:
                continue
            if code_uses_strings(dex, co, str_idxs):
                hits.append((cname, dex.method(midx)[1]))
    return hits


def find_callers(dex, target_method_idx):
    """反向查找调用了指定方法的所有方法（依赖分析法）"""
    callers = []
    for cname, cdo in dex.iter_classes():
        if not cdo:
            continue
        for midx, co in dex.iter_methods(cdo):
            if not co:
                continue
            d = dex.d
            size = struct.unpack_from('<I', d, co + 12)[0]
            base = co + 16
            for o in range(base, base + size * 2 - 3, 2):
                u = struct.unpack_from('<H', d, o)[0]
                if 0x6E <= (u & 0xFF) <= 0x72:
                    if struct.unpack_from('<H', d, o + 2)[0] == target_method_idx:
                        callers.append((cname, dex.method(midx)[1]))
                        break
    return callers


# ------------------------------------------------------------------ CLI 命令

def load_all_dex(apk_dir):
    """加载目录下所有 dex（支持解包后的目录，或直接是 apk 同目录）"""
    files = sorted(glob.glob(os.path.join(apk_dir, '*.dex')))
    if not files:
        raise SystemExit(f'目录下没找到 dex 文件: {apk_dir}')
    return [Dex(f) for f in files]


def cmd_strings(apk_dir, out_dir=None):
    """导出所有 dex 的字符串到文件，便于 grep"""
    out_dir = out_dir or os.path.join(apk_dir, 'strs')
    os.makedirs(out_dir, exist_ok=True)
    total = 0
    for f in sorted(glob.glob(os.path.join(apk_dir, '*.dex'))):
        dex = Dex(f)
        seen = set()
        for i in range(dex.string_ids_size):
            try:
                seen.add(dex.string(i))
            except Exception:
                pass
        out = os.path.join(out_dir, os.path.basename(f) + '.txt')
        with open(out, 'w', encoding='utf-8') as fh:
            for s in sorted(seen):
                if len(s) >= 3:
                    fh.write(s + '\n')
        total += len(seen)
        print(f'{os.path.basename(f):20s} {len(seen):>8d} 条')
    print(f'\n合计 {total} 条 → {out_dir}')


def cmd_apis(apk_dir):
    """
    提取 API 路径。

    注意：口令接口的路径常常不带 /api/ 前缀（例如网易云是裸的
    "password/url/decode/get"，只在签名时才拼 /api/），所以不能只匹配
    带前缀的路径，必须把「多段小写单词用斜杠连接」的形式也捞出来。
    """
    # 带前缀的常规路径
    pat_prefixed = re.compile(rb'/(?:e?api|weapi|openapi|rest|aweme|napi)/[a-zA-Z0-9_/\-]{2,90}')
    # 裸路径：2~4 段小写字母单词，如 password/url/decode/get
    pat_bare = re.compile(rb'(?<![a-zA-Z0-9_/])([a-z][a-z0-9]{1,20}(?:/[a-z][a-z0-9]{1,20}){1,4})(?![a-zA-Z0-9_/])')

    paths = set()
    for f in sorted(glob.glob(os.path.join(apk_dir, '*.dex'))):
        d = open(f, 'rb').read()
        for m in pat_prefixed.findall(d):
            paths.add(m.decode('latin1'))
        for m in pat_bare.findall(d):
            s = m.decode('latin1')
            # 过滤明显的类路径 / 资源路径 / 无意义组合
            if s.startswith(('android/', 'java/', 'kotlin/', 'com/', 'org/',
                             'androidx/', 'res/', 'assets/', 'lib/', 'meta-inf/')):
                continue
            if any(x in s for x in ('/', )) and len(s) >= 8:
                paths.add('/' + s)

    for p in sorted(paths):
        print(p)
    print(f'\n# 共 {len(paths)} 条', file=sys.stderr)


def cmd_find(apk_dir, keyword):
    """字符串反查：找出引用指定字符串的所有方法"""
    for dex in load_all_dex(apk_dir):
        hits = scan_strings_in_code(dex, keyword)
        if hits:
            print(f'=== {os.path.basename(dex.path)} ({len(hits)} 处)')
            for c, m in hits:
                print(f'  {c}->{m}')


def cmd_disasm(dex_file, class_name, method_name):
    """反汇编指定方法"""
    dex = Dex(dex_file)
    found = dex.find_method(class_name, method_name)
    if not found:
        print(f'未找到方法 {class_name}->{method_name}')
        return
    midx, co = found
    print(f'类: {class_name}')
    print(f'方法: {method_name} {dex.method(midx)[2]} -> {dex.method(midx)[3]}')
    print('-' * 70)
    for line in disasm_method(dex, co):
        print(line)


def cmd_methods(dex_file, class_name):
    """列出类的所有方法"""
    dex = Dex(dex_file)
    for cname, cdo in dex.iter_classes():
        if cname != class_name:
            continue
        print(f'{cname}')
        if not cdo:
            print('  (无方法)')
            return
        for midx, co in dex.iter_methods(cdo):
            if midx >= dex.method_ids_size:
                continue
            c, nm, ps, r = dex.method(midx)
            mark = 'code' if co else ''
            print(f'  {nm}({", ".join(ps)}){r}  {mark}')
        return
    print(f'未找到类 {class_name}')


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return

    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd == 'strings':
        cmd_strings(*args)
    elif cmd == 'apis':
        cmd_apis(*args)
    elif cmd == 'find':
        cmd_find(*args)
    elif cmd == 'disasm':
        cmd_disasm(*args)
    elif cmd == 'methods':
        cmd_methods(*args)
    else:
        print(__doc__)


if __name__ == '__main__':
    main()