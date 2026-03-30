#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GLTF Skin Fixer
修复Assimp导出的GLTF文件缺少skin引用的问题

使用方法:
    python fix_gltf_skin.py <input.gltf> [output.gltf]

    如果不指定output，则覆盖原文件
"""

import json
import sys
import argparse
from pathlib import Path


def fix_gltf_skin(input_path: str, output_path: str = None) -> bool:
    """
    修复GLTF文件，为每个mesh primitive添加skin引用

    Args:
        input_path: 输入GLTF文件路径
        output_path: 输出GLTF文件路径，默认为输入路径（覆盖）

    Returns:
        是否成功修复
    """
    input_file = Path(input_path)
    if not input_file.exists():
        print(f"错误: 文件不存在 {input_path}")
        return False

    if output_path is None:
        output_path = input_path

    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            gltf_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"错误: JSON解析失败 - {e}")
        return False
    except Exception as e:
        print(f"错误: 读取文件失败 - {e}")
        return False

    # 检查是否有skins
    skins = gltf_data.get('skins', [])
    if not skins:
        print("警告: GLTF文件中没有skins，无需修复")
        return False

    skin_count = len(skins)
    print(f"发现 {skin_count} 个skin(s)")

    # 检查meshes
    meshes = gltf_data.get('meshes', [])
    if not meshes:
        print("警告: GLTF文件中没有meshes")
        return False

    print(f"发现 {len(meshes)} 个mesh(es)")

    # 修复计数
    fixed_primitives = 0
    already_has_skin = 0

    # 为每个mesh的primitive添加skin引用
    for mesh_idx, mesh in enumerate(meshes):
        mesh_name = mesh.get('name', f'mesh_{mesh_idx}')
        primitives = mesh.get('primitives', [])

        for prim_idx, primitive in enumerate(primitives):
            # 检查是否已经有JOINTS_0属性（表示需要skin）
            attributes = primitive.get('attributes', {})
            has_joints = 'JOINTS_0' in attributes or 'JOINTS' in attributes

            if has_joints:
                if 'skin' in primitive:
                    already_has_skin += 1
                    print(f"  [跳过] {mesh_name} / primitive {prim_idx} 已有skin引用")
                else:
                    # 添加skin引用（默认使用第一个skin）
                    primitive['skin'] = 0
                    fixed_primitives += 1
                    print(f"  [修复] {mesh_name} / primitive {prim_idx} 添加skin引用")

    if fixed_primitives == 0:
        if already_has_skin > 0:
            print(f"\n所有 {already_has_skin} 个primitive已包含skin引用，无需修改")
            return True
        else:
            print("\n警告: 没有找到需要修复的primitive（没有带JOINTS属性的mesh）")
            return False

    # 保存修复后的文件
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(gltf_data, f, indent=2, ensure_ascii=False)

        print(f"\n修复完成:")
        print(f"  - 修复primitive: {fixed_primitives} 个")
        print(f"  - 已有skin引用: {already_has_skin} 个")
        print(f"  - 输出文件: {output_path}")
        return True

    except Exception as e:
        print(f"错误: 保存文件失败 - {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='修复GLTF文件的skin引用问题',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 修复并覆盖原文件
  python fix_gltf_skin.py model.gltf

  # 修复并保存到新文件
  python fix_gltf_skin.py model.gltf model_fixed.gltf

  # 批量修复目录中的所有gltf文件
  python fix_gltf_skin.py --batch ./models/
        """
    )

    parser.add_argument('input', help='输入GLTF文件或目录路径')
    parser.add_argument('output', nargs='?', help='输出GLTF文件路径（可选，默认覆盖）')
    parser.add_argument('--batch', '-b', action='store_true',
                        help='批量处理目录中的所有.gltf文件')
    parser.add_argument('--suffix', '-s', default='_fixed',
                        help='批量处理时的输出文件后缀（默认: _fixed）')

    args = parser.parse_args()

    input_path = Path(args.input)

    if args.batch or input_path.is_dir():
        # 批量处理
        if not input_path.is_dir():
            print(f"错误: 批量模式需要目录路径")
            sys.exit(1)

        gltf_files = list(input_path.glob('*.gltf')) + list(input_path.glob('*.glb'))
        if not gltf_files:
            print(f"在 {input_path} 中没有找到.gltf或.glb文件")
            sys.exit(1)

        print(f"批量处理 {len(gltf_files)} 个文件...\n")
        success_count = 0

        for gltf_file in gltf_files:
            output_file = gltf_file.parent / f"{gltf_file.stem}{args.suffix}{gltf_file.suffix}"
            print(f"处理: {gltf_file.name}")
            if fix_gltf_skin(str(gltf_file), str(output_file)):
                success_count += 1
            print()

        print(f"批量处理完成: {success_count}/{len(gltf_files)} 个文件成功")
    else:
        # 单文件处理
        if fix_gltf_skin(args.input, args.output):
            sys.exit(0)
        else:
            sys.exit(1)


if __name__ == '__main__':
    main()
