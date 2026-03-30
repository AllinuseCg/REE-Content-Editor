#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
诊断GLTF蒙皮问题
验证骨骼世界变换与逆绑定矩阵是否一致
"""

import json
import struct
import numpy as np
from pathlib import Path


def quaternion_to_matrix(q):
    """四元数转旋转矩阵 (x, y, z, w)"""
    x, y, z, w = q
    return np.array([
        [1 - 2*(y*y + z*z), 2*(x*y - z*w), 2*(x*z + y*w), 0],
        [2*(x*y + z*w), 1 - 2*(x*x + z*z), 2*(y*z - x*w), 0],
        [2*(x*z - y*w), 2*(y*z + x*w), 1 - 2*(x*x + y*y), 0],
        [0, 0, 0, 1]
    ])


def matrix_multiply(a, b):
    """4x4矩阵乘法"""
    return np.dot(a, b)


def get_node_local_matrix(node):
    """获取节点的局部变换矩阵"""
    if 'matrix' in node:
        return np.array(node['matrix']).reshape(4, 4)

    T = np.eye(4)
    R = np.eye(4)
    S = np.eye(4)

    if 'translation' in node:
        T[:3, 3] = node['translation']
    if 'rotation' in node:
        R = quaternion_to_matrix(node['rotation'])
    if 'scale' in node:
        S[0, 0] = node['scale'][0]
        S[1, 1] = node['scale'][1]
        S[2, 2] = node['scale'][2]

    return matrix_multiply(T, matrix_multiply(R, S))


def get_node_world_matrix(nodes, node_idx, cache=None):
    """计算节点的世界变换矩阵"""
    if cache is None:
        cache = {}
    if node_idx in cache:
        return cache[node_idx]

    node = nodes[node_idx]
    local_m = get_node_local_matrix(node)

    # 查找父级
    parent_idx = None
    for i, n in enumerate(nodes):
        if 'children' in n and node_idx in n['children']:
            parent_idx = i
            break

    if parent_idx is not None:
        parent_m = get_node_world_matrix(nodes, parent_idx, cache)
        world_m = matrix_multiply(parent_m, local_m)
    else:
        world_m = local_m

    cache[node_idx] = world_m
    return world_m


def check_gltf_skin(gltf_path):
    """检查GLTF蒙皮一致性"""
    gltf_file = Path(gltf_path)
    if not gltf_file.exists():
        print(f"错误: 找不到文件 {gltf_path}")
        return

    with open(gltf_file, 'r', encoding='utf-8') as f:
        gltf = json.load(f)

    nodes = gltf.get('nodes', [])
    skins = gltf.get('skins', [])
    accessors = gltf.get('accessors', [])
    buffer_views = gltf.get('bufferViews', [])

    if not skins:
        print("没有找到skins")
        return

    # 读取bin数据
    buffers = gltf.get('buffers', [])
    if buffers and 'uri' in buffers[0]:
        bin_path = gltf_file.parent / buffers[0]['uri']
    else:
        bin_path = gltf_file.parent / (gltf_file.stem + ".bin")

    if not bin_path.exists():
        print(f"错误: 找不到bin文件 {bin_path}")
        return

    with open(bin_path, 'rb') as f:
        buffer_data = f.read()

    for skin_idx, skin in enumerate(skins):
        print(f"\n=== Skin {skin_idx}: {skin.get('name', 'unnamed')} ===")
        print(f"Joints数量: {len(skin.get('joints', []))}")

        joints = skin.get('joints', [])
        ibm_accessor_idx = skin.get('inverseBindMatrices')

        if ibm_accessor_idx is None:
            print("没有inverseBindMatrices")
            continue

        accessor = accessors[ibm_accessor_idx]
        bv_idx = accessor['bufferView']
        bv = buffer_views[bv_idx]
        offset = bv.get('byteOffset', 0)
        stride = bv.get('byteStride', 64)

        mismatch_count = 0
        identity_count = 0

        # 检查前10个joint
        check_count = min(10, len(joints))
        print(f"\n检查前{check_count}个joint的一致性:")

        matrices_cache = {}

        for i in range(check_count):
            joint_idx = joints[i]

            # 读取逆绑定矩阵
            matrix_offset = offset + i * stride
            matrix_data = buffer_data[matrix_offset:matrix_offset + 64]
            floats = struct.unpack('16f', matrix_data)
            ibm = np.array(floats).reshape(4, 4)

            # 计算节点的世界变换
            try:
                world_m = get_node_world_matrix(nodes, joint_idx, matrices_cache)
            except Exception as e:
                print(f"  Joint {i} (Node {joint_idx}): 无法计算世界变换 - {e}")
                continue

            # 检查世界变换 * 逆绑定矩阵是否接近单位矩阵
            combined = matrix_multiply(world_m, ibm)
            identity = np.eye(4)
            diff = np.abs(combined - identity)
            max_diff = np.max(diff)

            if max_diff < 0.01:
                identity_count += 1
                status = "OK"
            else:
                mismatch_count += 1
                status = "FAIL"

            node_name = nodes[joint_idx].get('name', f'unnamed_{joint_idx}')
            print(f"  [{status}] Joint {i} ({node_name}): max_diff={max_diff:.4f}")

            if max_diff > 0.01:
                print(f"      世界变换:\n{world_m}")
                print(f"      逆绑定矩阵:\n{ibm}")

        print(f"\n  结果: 匹配 {identity_count}/{check_count}, 不匹配 {mismatch_count}/{check_count}")


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("用法: python check_skin_consistency.py <input.gltf>")
        sys.exit(1)

    check_gltf_skin(sys.argv[1])
