#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GLTF逆绑定矩阵转置修复工具
修复Assimp导出导致的矩阵转置不一致问题
"""

import json
import struct
import argparse
from pathlib import Path


def transpose_matrices_in_buffer(buffer_data, offset, count, stride=64):
    """
    转置bin文件中指定位置的矩阵

    Args:
        buffer_data: bytearray类型的buffer数据
        offset: 起始偏移
        count: 矩阵数量
        stride: 每个矩阵的字节数（默认64=16个float）

    Returns:
        修改后的bytearray
    """
    data = bytearray(buffer_data)

    for i in range(count):
        matrix_offset = offset + i * stride

        # 读取16个float
        floats = struct.unpack_from('16f', data, matrix_offset)

        # 转置矩阵 (行主序 <-> 列主序)
        # 原始: M00 M01 M02 M03 M04 M05 M06 M07 M08 M09 M10 M11 M12 M13 M14 M15
        # 转置: M00 M04 M08 M12 M01 M05 M09 M13 M02 M06 M10 M14 M03 M07 M11 M15
        transposed = (
            floats[0], floats[4], floats[8], floats[12],
            floats[1], floats[5], floats[9], floats[13],
            floats[2], floats[6], floats[10], floats[14],
            floats[3], floats[7], floats[11], floats[15]
        )

        # 写回
        struct.pack_into('16f', data, matrix_offset, *transposed)

    return data


def fix_gltf_inverse_bind_matrices(input_path, output_path=None, backup=True):
    """
    修复GLTF文件的逆绑定矩阵转置问题

    Args:
        input_path: 输入GLTF文件路径
        output_path: 输出GLTF文件路径（默认覆盖原文件）
        backup: 是否备份原文件

    Returns:
        是否成功
    """
    input_file = Path(input_path)
    if not input_file.exists():
        print(f"错误: 文件不存在 {input_path}")
        return False

    # 读取GLTF JSON
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            gltf = json.load(f)
    except Exception as e:
        print(f"错误: 读取GLTF文件失败 - {e}")
        return False

    # 检查是否有skins
    skins = gltf.get('skins', [])
    if not skins:
        print("警告: GLTF文件中没有skins，无需修复")
        return False

    accessors = gltf.get('accessors', [])
    buffer_views = gltf.get('bufferViews', [])
    buffers = gltf.get('buffers', [])

    # 找到对应的bin文件
    if buffers and 'uri' in buffers[0]:
        bin_uri = buffers[0]['uri']
    else:
        bin_uri = input_file.stem + ".bin"

    bin_path = input_file.parent / bin_uri
    if not bin_path.exists():
        print(f"错误: 找不到bin文件 {bin_path}")
        return False

    # 读取bin数据
    try:
        with open(bin_path, 'rb') as f:
            buffer_data = bytearray(f.read())
    except Exception as e:
        print(f"错误: 读取bin文件失败 - {e}")
        return False

    print(f"加载: {input_file.name}")
    print(f"Bin文件: {bin_path.name}")
    print(f"发现 {len(skins)} 个skin(s)")

    # 备份原文件
    if backup:
        backup_gltf = input_file.with_suffix('.gltf.backup')
        backup_bin = bin_path.with_suffix('.bin.backup')
        try:
            with open(backup_gltf, 'w', encoding='utf-8') as f:
                json.dump(gltf, f)
            with open(backup_bin, 'wb') as f:
                f.write(buffer_data)
            print(f"已备份到: {backup_gltf.name}, {backup_bin.name}")
        except Exception as e:
            print(f"警告: 备份失败 - {e}")

    # 处理每个skin
    total_matrices = 0
    for skin_idx, skin in enumerate(skins):
        ibm_accessor_idx = skin.get('inverseBindMatrices')
        if ibm_accessor_idx is None:
            print(f"  Skin {skin_idx}: 没有inverseBindMatrices，跳过")
            continue

        joints = skin.get('joints', [])
        accessor = accessors[ibm_accessor_idx]
        bv_idx = accessor['bufferView']
        bv = buffer_views[bv_idx]

        offset = bv.get('byteOffset', 0)
        count = accessor['count']
        stride = bv.get('byteStride', 64)

        print(f"  Skin {skin_idx}: 转置 {count} 个矩阵 (joints: {len(joints)})")

        # 转置矩阵
        buffer_data = transpose_matrices_in_buffer(buffer_data, offset, count, stride)
        total_matrices += count

    # 保存修复后的文件
    if output_path is None:
        output_path = input_path
        output_bin_path = bin_path
    else:
        output_bin_path = Path(output_path).parent / bin_uri

    try:
        # 保存GLTF（JSON部分不变）
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(gltf, f, indent=2, ensure_ascii=False)

        # 保存bin（转置后的数据）
        with open(output_bin_path, 'wb') as f:
            f.write(buffer_data)

        print(f"\n修复完成!")
        print(f"  - 转置矩阵: {total_matrices} 个")
        print(f"  - 输出GLTF: {output_path}")
        print(f"  - 输出BIN: {output_bin_path}")
        return True

    except Exception as e:
        print(f"错误: 保存文件失败 - {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='修复GLTF逆绑定矩阵转置问题',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 修复并覆盖原文件（自动备份）
  python fix_ibm_transpose.py model.gltf

  # 修复并保存到新文件
  python fix_ibm_transpose.py model.gltf model_fixed.gltf

  # 修复但不备份
  python fix_ibm_transpose.py model.gltf --no-backup
        """
    )

    parser.add_argument('input', help='输入GLTF文件路径')
    parser.add_argument('output', nargs='?', help='输出GLTF文件路径（可选，默认覆盖）')
    parser.add_argument('--no-backup', action='store_true',
                        help='不备份原文件')

    args = parser.parse_args()

    success = fix_gltf_inverse_bind_matrices(
        args.input,
        args.output,
        backup=not args.no_backup
    )

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    import sys
    main()
