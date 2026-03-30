#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GLTF Inverse Bind Matrices 分析工具
用于检查和诊断蒙皮问题
"""

import json
import struct
import argparse
from pathlib import Path


def read_buffer_data(gltf_path, bin_path):
    """读取bin文件中的二进制数据"""
    if not bin_path.exists():
        print(f"错误: 找不到bin文件 {bin_path}")
        return None

    with open(bin_path, 'rb') as f:
        return f.read()


def analyze_inverse_bind_matrices(gltf_path):
    """分析GLTF中的逆绑定矩阵"""
    gltf_file = Path(gltf_path)
    if not gltf_file.exists():
        print(f"错误: 找不到文件 {gltf_path}")
        return

    with open(gltf_file, 'r', encoding='utf-8') as f:
        gltf = json.load(f)

    # 获取skins
    skins = gltf.get('skins', [])
    if not skins:
        print("没有找到skins")
        return

    accessors = gltf.get('accessors', [])
    buffer_views = gltf.get('bufferViews', [])

    # 找到对应的bin文件
    bin_path = gltf_file.parent / gltf_file.stem / '.bin'
    if not bin_path.exists():
        # 尝试从buffers中获取uri
        buffers = gltf.get('buffers', [])
        if buffers and 'uri' in buffers[0]:
            bin_uri = buffers[0]['uri']
            bin_path = gltf_file.parent / bin_uri

    buffer_data = read_buffer_data(gltf_path, bin_path)
    if buffer_data is None:
        return

    for skin_idx, skin in enumerate(skins):
        print(f"\n=== Skin {skin_idx}: {skin.get('name', 'unnamed')} ===")

        joints = skin.get('joints', [])
        print(f"Joints数量: {len(joints)}")

        ibm_accessor_idx = skin.get('inverseBindMatrices')
        if ibm_accessor_idx is None:
            print("没有inverseBindMatrices")
            continue

        accessor = accessors[ibm_accessor_idx]
        print(f"Accessor索引: {ibm_accessor_idx}")
        print(f"  Count: {accessor['count']}")
        print(f"  Type: {accessor['type']}")
        print(f"  ComponentType: {accessor['componentType']}")

        # 获取buffer view
        bv_idx = accessor['bufferView']
        bv = buffer_views[bv_idx]

        offset = bv.get('byteOffset', 0)
        stride = bv.get('byteStride', 64)  # MAT4 = 16 floats = 64 bytes

        # 读取前3个矩阵
        print("\n前3个逆绑定矩阵:")
        for i in range(min(3, accessor['count'])):
            matrix_offset = offset + i * stride
            # 读取16个float（4x4矩阵）
            matrix_data = buffer_data[matrix_offset:matrix_offset + 64]
            floats = struct.unpack('16f', matrix_data)

            print(f"\n  Joint {i} (Node {joints[i]}):")
            print(f"    [{floats[0]:8.4f} {floats[1]:8.4f} {floats[2]:8.4f} {floats[3]:8.4f}]")
            print(f"    [{floats[4]:8.4f} {floats[5]:8.4f} {floats[6]:8.4f} {floats[7]:8.4f}]")
            print(f"    [{floats[8]:8.4f} {floats[9]:8.4f} {floats[10]:8.4f} {floats[11]:8.4f}]")
            print(f"    [{floats[12]:8.4f} {floats[13]:8.4f} {floats[14]:8.4f} {floats[15]:8.4f}]")

            # 检查矩阵是否合理（平移部分通常较小）
            tx, ty, tz = floats[12], floats[13], floats[14]
            if abs(tx) > 1000 or abs(ty) > 1000 or abs(tz) > 1000:
                print(f"    ⚠️ 警告: 平移值过大 ({tx:.2f}, {ty:.2f}, {tz:.2f})")

        # 检查所有矩阵的统计信息
        print("\n矩阵统计信息:")
        large_translation = 0
        identity_matrices = 0
        for i in range(accessor['count']):
            matrix_offset = offset + i * stride
            matrix_data = buffer_data[matrix_offset:matrix_offset + 64]
            floats = struct.unpack('16f', matrix_data)
            tx, ty, tz = floats[12], floats[13], floats[14]
            if abs(tx) > 1000 or abs(ty) > 1000 or abs(tz) > 1000:
                large_translation += 1
            # 检查是否接近单位矩阵
            if (abs(floats[0]-1) < 0.01 and abs(floats[5]-1) < 0.01 and
                abs(floats[10]-1) < 0.01 and abs(floats[15]-1) < 0.01 and
                abs(floats[1]) < 0.01 and abs(floats[2]) < 0.01 and abs(floats[3]) < 0.01):
                identity_matrices += 1

        print(f"  单位矩阵数量: {identity_matrices}/{accessor['count']}")
        print(f"  平移值过大的矩阵: {large_translation}/{accessor['count']}")


def transpose_matrices(gltf_path, output_path):
    """转置所有逆绑定矩阵（尝试修复）"""
    gltf_file = Path(gltf_path)
    if not gltf_file.exists():
        print(f"错误: 找不到文件 {gltf_path}")
        return

    with open(gltf_file, 'r', encoding='utf-8') as f:
        gltf = json.load(f)

    # 找到对应的bin文件
    bin_uri = gltf['buffers'][0]['uri']
    bin_path = gltf_file.parent / bin_uri
    bin_output_path = Path(output_path).parent / bin_uri

    if not bin_path.exists():
        print(f"错误: 找不到bin文件 {bin_path}")
        return

    # 读取bin数据
    with open(bin_path, 'rb') as f:
        buffer_data = bytearray(f.read())

    accessors = gltf.get('accessors', [])
    buffer_views = gltf.get('bufferViews', [])
    skins = gltf.get('skins', [])

    for skin in skins:
        ibm_accessor_idx = skin.get('inverseBindMatrices')
        if ibm_accessor_idx is None:
            continue

        accessor = accessors[ibm_accessor_idx]
        bv_idx = accessor['bufferView']
        bv = buffer_views[bv_idx]

        offset = bv.get('byteOffset', 0)
        stride = bv.get('byteStride', 64)
        count = accessor['count']

        print(f"转置Skin的 {count} 个矩阵...")

        for i in range(count):
            matrix_offset = offset + i * stride
            # 读取矩阵
            matrix_data = buffer_data[matrix_offset:matrix_offset + 64]
            floats = list(struct.unpack('16f', matrix_data))

            # 转置矩阵 (列主序 -> 行主序 或反之)
            # 原始布局: M00 M01 M02 M03 M04 M05 M06 M07 M08 M09 M10 M11 M12 M13 M14 M15
            # 转置后:   M00 M04 M08 M12 M01 M05 M09 M13 M02 M06 M10 M14 M03 M07 M11 M15
            transposed = [
                floats[0], floats[4], floats[8], floats[12],
                floats[1], floats[5], floats[9], floats[13],
                floats[2], floats[6], floats[10], floats[14],
                floats[3], floats[7], floats[11], floats[15]
            ]

            # 写回
            buffer_data[matrix_offset:matrix_offset + 64] = struct.pack('16f', *transposed)

    # 保存修改后的文件
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(gltf, f, indent=2, ensure_ascii=False)

    with open(bin_output_path, 'wb') as f:
        f.write(buffer_data)

    print(f"已保存到: {output_path} 和 {bin_output_path}")


def main():
    parser = argparse.ArgumentParser(description='分析GLTF逆绑定矩阵')
    parser.add_argument('input', help='输入GLTF文件')
    parser.add_argument('--output', '-o', help='输出文件路径（用于转置修复）')
    parser.add_argument('--transpose', '-t', action='store_true',
                        help='转置逆绑定矩阵并保存')

    args = parser.parse_args()

    if args.transpose and args.output:
        transpose_matrices(args.input, args.output)
    else:
        analyze_inverse_bind_matrices(args.input)


if __name__ == '__main__':
    main()
