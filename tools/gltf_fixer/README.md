# GLTF Skin Fixer

修复Assimp导出的GLTF/GLB文件中的多个问题，使其能在虚幻引擎中正确显示蒙皮。

## 问题列表

### 问题1: Mesh缺少skin引用
使用Assimp导出GLTF时，mesh primitives缺少对skin的引用，导致虚幻引擎无法识别蒙皮。

### 问题2: 逆绑定矩阵转置错误
Assimp导出的GLTF中，骨骼Transform和逆绑定矩阵的矩阵存储顺序不一致（一个行主序，一个列主序），导致蒙皮扭曲。

## 工具列表

| 工具 | 功能 | 使用场景 |
|-----|------|---------|
| `fix_gltf_skin.py` | 添加缺失的skin引用 | 虚幻引擎无法识别蒙皮 |
| `fix_ibm_transpose.py` | 修复逆绑定矩阵转置 | 蒙皮扭曲/变形 |
| `check_skin_consistency.py` | 验证骨骼与逆绑定矩阵一致性 | 诊断蒙皮问题 |
| `analyze_ibm.py` | 分析逆绑定矩阵数据 | 调试矩阵问题 |

## 使用方法

### 标准修复流程（推荐）

```bash
# 第1步: 修复skin引用
python fix_gltf_skin.py model.gltf model_step1.gltf

# 第2步: 修复逆绑定矩阵转置
python fix_ibm_transpose.py model_step1.gltf model_fixed.gltf
```

### 单工具使用

#### fix_gltf_skin.py - 修复skin引用

```bash
# 修复并覆盖原文件
python fix_gltf_skin.py model.gltf

# 修复并保存到新文件
python fix_gltf_skin.py model.gltf model_fixed.gltf

# 批量修复
python fix_gltf_skin.py --batch ./models/
```

#### fix_ibm_transpose.py - 修复矩阵转置

```bash
# 修复并覆盖原文件（自动备份）
python fix_ibm_transpose.py model.gltf

# 修复并保存到新文件
python fix_ibm_transpose.py model.gltf model_fixed.gltf

# 不备份
python fix_ibm_transpose.py model.gltf --no-backup
```

#### check_skin_consistency.py - 验证一致性

```bash
# 检查GLTF文件中的骨骼世界变换与逆绑定矩阵是否匹配
python check_skin_consistency.py model.gltf
```

输出示例:
```
=== Skin 0: skin ===
Joints数量: 279

检查前10个joint的一致性:
  [OK] Joint 0 (root): max_diff=0.0000
  [OK] Joint 1 (Ground_Angle): max_diff=0.0000
  [FAIL] Joint 2 (COG): max_diff=1.0404  ← 不匹配，需要修复
  ...

结果: 匹配 2/10, 不匹配 8/10
```

## 修复内容详解

### fix_gltf_skin.py
- 遍历所有mesh和primitive
- 检测带有JOINTS_0属性的primitive（需要蒙皮的）
- 为缺少skin引用的primitive添加 `"skin": 0`
- 保留已有的skin引用

### fix_ibm_transpose.py
- 读取bin文件中的二进制数据
- 找到inverseBindMatrices对应的数据区域
- 对每个4x4矩阵进行转置（行主序 ↔ 列主序）
- 保存修改后的GLTF和bin文件

## 依赖

- Python 3.6+
- 无第三方库依赖（使用标准库）
- `check_skin_consistency.py` 需要 numpy（可选）

## 在REE Content Editor中的完整使用流程

1. 从REE Content Editor导出GLTF/GLB
2. 如果是.gltf格式，确保对应的.bin文件存在
3. 运行修复脚本:
   ```bash
   python fix_gltf_skin.py exported.gltf
   python fix_ibm_transpose.py exported.gltf
   ```
4. 可选: 验证修复结果
   ```bash
   python check_skin_consistency.py exported.gltf
   ```
5. 导入虚幻引擎验证蒙皮

## 故障排除

### 蒙皮不显示
- 运行 `fix_gltf_skin.py` 添加skin引用

### 蒙皮扭曲/变形
- 运行 `fix_ibm_transpose.py` 修复矩阵转置
- 使用 `check_skin_consistency.py` 验证

### 部分骨骼正常，部分扭曲
- 可能是骨骼权重超过4个（Assimp GLTF导出限制）
- 考虑使用FBX格式或合并骨骼权重
