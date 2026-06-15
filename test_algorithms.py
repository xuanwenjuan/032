import sys
import os
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

import numpy as np

print("=" * 60)
print("MIT脑水肿监测系统 - 后端算法测试")
print("=" * 60)

print("\n[1] 测试基础模块导入...")
try:
    from app.algorithms.forward_solver import (
        create_brain_mask,
        create_conductivity_map,
        ForwardSolverFDM,
        ElectrodeConfig
    )
    print("  ✓ forward_solver 模块导入成功")
except Exception as e:
    print(f"  ✗ forward_solver 导入失败: {e}")
    sys.exit(1)

try:
    from app.algorithms.reconstruction import (
        LinearBackProjection,
        run_complete_simulation_2d
    )
    print("  ✓ reconstruction 模块导入成功")
except Exception as e:
    print(f"  ✗ reconstruction 导入失败: {e}")
    sys.exit(1)

try:
    from app.algorithms.simulation_3d import (
        create_3d_brain_mask,
        create_3d_conductivity_map,
        reconstruct_3d_lbp
    )
    print("  ✓ simulation_3d 模块导入成功")
except Exception as e:
    print(f"  ✗ simulation_3d 导入失败: {e}")
    sys.exit(1)

print("\n[2] 测试脑部掩码生成...")
mask = create_brain_mask(16)
print(f"  ✓ 16×16 脑部掩码: {mask.sum()} 个有效像素")

mask3d = create_3d_brain_mask(8, 8, 4)
print(f"  ✓ 8×8×4 3D脑部掩码: {mask3d.sum()} 个有效像素")

print("\n[3] 测试电导率图生成...")
edema_regions = [
    {"center_x": 8, "center_y": 6, "radius": 2, "conductivity_factor": 2.0}
]
sigma = create_conductivity_map(16, edema_regions)
print(f"  ✓ 电导率图范围: [{sigma.min():.3f}, {sigma.max():.3f}]")
print(f"  ✓ 水肿区域平均电导率: {sigma[5:9, 3:9].mean():.3f}")

print("\n[4] 测试完整2D仿真流程（可能需要几秒）...")
try:
    result = run_complete_simulation_2d(
        grid_size=16,
        edema_regions=edema_regions
    )
    recon = np.array(result["reconstructed_conductivity"])
    print(f"  ✓ 重建图像范围: [{recon.min():.3f}, {recon.max():.3f}]")
    print(f"  ✓ 重建图像尺寸: {recon.shape}")
    print(f"  ✓ 测量数据点: {len(result['measurements'])}")
    print("  ✓ 2D仿真流程测试通过!")
except Exception as e:
    print(f"  ✗ 2D仿真失败: {e}")
    import traceback
    traceback.print_exc()

print("\n[5] 测试3D重建算法（简化版）...")
try:
    result3d = reconstruct_3d_lbp(8, 8, 4, edema_regions)
    mid = np.array(result3d["mid_slice"])
    print(f"  ✓ 3D重建中切片尺寸: {mid.shape}")
    print(f"  ✓ 3D切片数量: {len(result3d['reconstruction_3d'])}")
    print("  ✓ 3D重建算法测试通过!")
except Exception as e:
    print(f"  ✗ 3D重建失败: {e}")

print("\n[6] 测试图像工具模块...")
try:
    from app.services.image_utils import matrix_to_base64, drawn_mask_to_edema_regions
    test_matrix = np.random.rand(16, 16).tolist()
    b64 = matrix_to_base64(test_matrix)
    print(f"  ✓ Base64图像长度: {len(b64)} 字符")
    print(f"  ✓ 图像数据头: data:image/png;base64,{b64[:20]}...")

    test_mask = np.zeros((16, 16), dtype=int)
    test_mask[6:10, 6:10] = 1
    regions = drawn_mask_to_edema_regions(test_mask.tolist())
    print(f"  ✓ 绘制掩码识别区域: {len(regions)} 个")
    print("  ✓ 图像工具模块测试通过!")
except Exception as e:
    print(f"  ✗ 图像工具测试失败: {e}")

print("\n" + "=" * 60)
print("所有核心算法测试完成!")
print("=" * 60)
